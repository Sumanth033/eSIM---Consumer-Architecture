

import abc
import typing
from typing import List, Dict, Optional
from termcolor import colored
from construct import Byte, GreedyBytes
from construct import Optional as COptional
from osmocom.construct import *
from osmocom.utils import *

from backend.runtime import RuntimeLchan, RuntimeState, lchan_nr_from_cla
from backend.filesystem import CardADF, CardFile, TransparentEF, LinFixedEF

"""There are multiple levels of decode:

    1) pure TPDU / APDU level (no filesystem state required to decode)
        1a) the raw C-TPDU + R-TPDU
        1b) the raw C-APDU + R-APDU
        1c) the C-APDU + R-APDU split in its portions (p1/p2/lc/le/cmd/rsp)
        1d) the abstract C-APDU + R-APDU (mostly p1/p2 parsing; SELECT response)
    2) the decoded DATA of command/response APDU
        * READ/UPDATE: requires state/context: which file is selected? how to decode it?
"""

class ApduCommandMeta(abc.ABCMeta):
    """A meta-class that we can use to set some class variables when declaring
       a derived class of ApduCommand."""
    def __new__(mcs, name, bases, namespace, **kwargs):
        x = super().__new__(mcs, name, bases, namespace)
        x._name = namespace.get('name', kwargs.get('n', None))
        x._ins = namespace.get('ins', kwargs.get('ins', None))
        x._cla = namespace.get('cla', kwargs.get('cla', None))
        return x

BytesOrHex = typing.Union[bytes, Hexstr]

class Tpdu:
    def __init__(self, cmd: BytesOrHex, rsp: Optional[BytesOrHex] = None):
        if isinstance(cmd, str):
            self.cmd = h2b(cmd)
        else:
            self.cmd = cmd
        if  isinstance(rsp, str):
            self.rsp = h2b(rsp)
        else:
            self.rsp = rsp

    def __str__(self):
        return '%s(%02X %02X %02X %02X %02X %s %s %s)' % (type(self).__name__, self.cla, self.ins, self.p1,
                self.p2, self.p3, b2h(self.cmd_data), b2h(self.rsp_data), b2h(self.sw))

    @property
    def cla(self) -> int:
        """Return CLA of the C-APDU Header."""
        return self.cmd[0]

    @property
    def ins(self) -> int:
        """Return INS of the C-APDU Header."""
        return self.cmd[1]

    @property
    def p1(self) -> int:
        """Return P1 of the C-APDU Header."""
        return self.cmd[2]

    @property
    def p2(self) -> int:
        """Return P2 of the C-APDU Header."""
        return self.cmd[3]

    @property
    def p3(self) -> int:
        """Return P3 of the C-APDU Header."""
        return self.cmd[4]

    @property
    def cmd_data(self) -> int:
        """Return the DATA portion of the C-APDU"""
        return self.cmd[5:]

    @property
    def sw(self) -> Optional[bytes]:
        """Return Status Word (SW) of the R-APDU"""
        return self.rsp[-2:] if self.rsp else None

    @property
    def rsp_data(self) -> Optional[bytes]:
        """Return the DATA portion of the R-APDU"""
        return self.rsp[:-2] if self.rsp else None


class Apdu(Tpdu):
    @property
    def lc(self) -> int:
        """Return Lc; Length of C-APDU body."""
        return len(self.cmd_data)

    @property
    def lr(self) -> int:
        """Return Lr; Length of R-APDU body."""
        return len(self.rsp_data)

    @property
    def successful(self) -> bool:
        """Was the execution of this APDU successful?"""
        method = getattr(self, '_is_success', None)
        if callable(method):
            return method()
        # default case: only 9000 is success
        if self.sw == b'\x90\x00':
            return True
        # This is not really a generic positive APDU SW but specific to UICC/SIM
        if self.sw[0] == 0x91:
            return True
        return False


class ApduCommand(Apdu, metaclass=ApduCommandMeta):
    """Base class from which you would derive individual commands/instructions like SELECT.
       A derived class represents a decoder for a specific instruction.
       An instance of such a derived class is one concrete APDU."""
    # fall-back constructs if the derived class provides no override
    _construct_p1 = Byte
    _construct_p2 = Byte
    _construct = GreedyBytes
    _construct_rsp = GreedyBytes
    _tlv = None
    _tlv_rsp = None

    def __init__(self, cmd: BytesOrHex, rsp: Optional[BytesOrHex] = None):
        """Instantiate a new ApduCommand from give cmd + resp."""
        # store raw data
        super().__init__(cmd, rsp)
        # default to 'empty' ID column. To be set to useful values (like record number)
        # by derived class {cmd_rsp}_to_dict() or process() methods
        self.col_id = '-'
        # fields only set by process_* methods
        self.file = None
        self.lchan = None
        self.processed = None
        # the methods below could raise exceptions and those handlers might assume cmd_{dict,resp}
        self.cmd_dict = None
        self.rsp_dict = None
        # interpret the data
        self.cmd_dict = self.cmd_to_dict()
        self.rsp_dict = self.rsp_to_dict() if self.rsp else {}


    @classmethod
    def from_apdu(cls, apdu:Apdu, **kwargs) -> 'ApduCommand':
        """Instantiate an ApduCommand from an existing APDU."""
        return cls(cmd=apdu.cmd, rsp=apdu.rsp, **kwargs)

    @classmethod
    def from_bytes(cls, buffer:bytes) -> 'ApduCommand':
        """Instantiate an ApduCommand from a linear byte buffer containing hdr,cmd,rsp,sw.
        This is for example used when parsing GSMTAP traces that traditionally contain the
        full command and response portion in one packet: "CLA INS P1 P2 P3 DATA SW" and we
        now need to figure out whether the DATA part is part of the CMD or the RSP"""
        apdu_case = cls.get_apdu_case(buffer)
        if apdu_case in [1, 2]:
            # data is part of response
            return cls(buffer[:5], buffer[5:])
        if apdu_case in [3, 4]:
            # data is part of command
            lc = buffer[4]
            return cls(buffer[:5+lc], buffer[5+lc:])
        raise ValueError('%s: Invalid APDU Case %u' % (cls.__name__, apdu_case))

    @property
    def path(self) -> List[str]:
        """Return (if known) the path as list of files to the file on which this command operates."""
        if self.file:
            return self.file.fully_qualified_path()
        return []

    @property
    def path_str(self) -> str:
        """Return (if known) the path as string to the file on which this command operates."""
        if self.file:
            return self.file.fully_qualified_path_str()
        return ''

    @property
    def col_sw(self) -> str:
        """Return the ansi-colorized status word. Green==OK, Red==Error"""
        if self.successful:
            return colored(b2h(self.sw), 'green')
        return colored(b2h(self.sw), 'red')

    @property
    def lchan_nr(self) -> int:
        """Logical channel number over which this ApduCommand was transmitted."""
        if self.lchan:
            return self.lchan.lchan_nr
        return lchan_nr_from_cla(self.cla)

    def __str__(self) -> str:
        return '%02u %s(%s): %s' % (self.lchan_nr, type(self).__name__, self.path_str, self.to_dict())

    def __repr__(self) -> str:
        return '%s(INS=%02x,CLA=%s)' % (self.__class__, self.ins, self.cla)

    def _process_fallback(self, rs: RuntimeState):
        """Fall-back function to be called if there is no derived-class-specific
        process_global or process_on_lchan method. Uses information from APDU decode."""
        self.processed = {}
        if 'p1' not in self.cmd_dict:
            self.processed = self.to_dict()
        else:
            self.processed['p1'] = self.cmd_dict['p1']
            self.processed['p2'] = self.cmd_dict['p2']
            if 'body' in self.cmd_dict and self.cmd_dict['body']:
                self.processed['cmd'] = self.cmd_dict['body']
            if 'body' in self.rsp_dict and self.rsp_dict['body']:
                self.processed['rsp'] = self.rsp_dict['body']
        return self.processed

    def process(self, rs: RuntimeState):
        # if there is a global method, use that; else use process_on_lchan
        method = getattr(self, 'process_global', None)
        if callable(method):
            self.processed = method(rs)
            return self.processed
        method = getattr(self, 'process_on_lchan', None)
        if callable(method):
            self.lchan = rs.get_lchan_by_cla(self.cla)
            self.processed = method(self.lchan)
            return self.processed
        # if none of the two methods exist:
        return self._process_fallback(rs)

    @classmethod
    def get_apdu_case(cls, hdr:bytes) -> int:
        if hasattr(cls, '_apdu_case'):
            return cls._apdu_case
        method = getattr(cls, '_get_apdu_case', None)
        if callable(method):
            return method(hdr)
        raise ValueError('%s: Class definition missing _apdu_case attribute or _get_apdu_case method' % cls.__name__)

    @classmethod
    def match_cla(cls, cla) -> bool:
        """Does the given CLA match the CLA list of the command?."""
        if not isinstance(cla, str):
            cla = '%02X' % cla
        cla = cla.upper()
        # see https://github.com/PyCQA/pylint/issues/7219
        # pylint: disable=no-member
        for cla_match in cls._cla:
            cla_masked = ""
            for i in range(0, 2):
                if cla_match[i] == 'X':
                    cla_masked += 'X'
                else:
                    cla_masked += cla[i]
            if cla_masked == cla_match.upper():
                return True
        return False

    def cmd_to_dict(self) -> Dict:
        """Convert the Command part of the APDU to a dict."""
        method = getattr(self, '_decode_cmd', None)
        if callable(method):
            return method()
        else:
            return self._cmd_to_dict()

    def _cmd_to_dict(self) -> Dict:
        """back-end function performing automatic decoding using _construct / _tlv."""
        r = {}
        method = getattr(self, '_decode_p1p2', None)
        if callable(method):
            r = self._decode_p1p2()
        else:
            r['p1'] = parse_construct(self._construct_p1, self.p1.to_bytes(1, 'big'))
            r['p2'] = parse_construct(self._construct_p2, self.p2.to_bytes(1, 'big'))
        r['p3'] = self.p3
        if self.cmd_data:
            if self._tlv:
                ie = self._tlv()
                ie.from_tlv(self.cmd_data)
                r['body'] = ie.to_dict()
            else:
                r['body'] = parse_construct(self._construct, self.cmd_data)
        return r

    def rsp_to_dict(self) -> Dict:
        """Convert the Response part of the APDU to a dict."""
        method = getattr(self, '_decode_rsp', None)
        if callable(method):
            return method()
        else:
            r = {}
            if self.rsp_data:
                if self._tlv_rsp:
                    ie = self._tlv_rsp()
                    ie.from_tlv(self.rsp_data)
                    r['body'] = ie.to_dict()
                else:
                    r['body'] = parse_construct(self._construct_rsp, self.rsp_data)
            r['sw'] = b2h(self.sw)
            return r

    def to_dict(self) -> Dict:
        """Convert the entire APDU to a dict."""
        return {'cmd': self.cmd_dict, 'rsp': self.rsp_dict}

    def to_json(self) -> str:
        """Convert the entire APDU to JSON."""
        d = self.to_dict()
        return json.dumps(d)

    def _determine_file(self, lchan) -> CardFile:
        """Helper function for read/update commands that might use SFI instead of selected file.
        Expects that the self.cmd_dict has already been populated with the 'file' member."""
        if self.cmd_dict['file'] == 'currently_selected_ef':
            self.file = lchan.selected_file
        elif self.cmd_dict['file'] == 'sfi':
            cwd = lchan.get_cwd()
            self.file = cwd.lookup_file_by_sfid(self.cmd_dict['sfi'])


class ApduCommandSet:
    """A set of card instructions, typically specified within one spec."""

    def __init__(self, name: str, cmds: List[ApduCommand] =[]):
        self.name = name
        self.cmds = {c._ins: c for c in cmds}

    def __str__(self) -> str:
        return self.name

    def __getitem__(self, idx) -> ApduCommand:
        return self.cmds[idx]

    def __add__(self, other) -> 'ApduCommandSet':
        if isinstance(other, ApduCommand):
            if other.ins in self.cmds:
                raise ValueError('%s: INS 0x%02x already defined: %s' %
                                 (self, other.ins, self.cmds[other.ins]))
            self.cmds[other.ins] = other
        elif isinstance(other, ApduCommandSet):
            for c in other.cmds.keys():
                self.cmds[c] = other.cmds[c]
        else:
            raise ValueError(
                '%s: Unsupported type to add operator: %s' % (self, other))
        return self

    def lookup(self, ins, cla=None) -> Optional[ApduCommand]:
        """look-up the command within the CommandSet."""
        ins = int(ins)
        if not ins in self.cmds:
            return None
        cmd = self.cmds[ins]
        if cla and not cmd.match_cla(cla):
            return None
        return cmd

    def parse_cmd_apdu(self, apdu: Apdu) -> ApduCommand:
        """Parse a Command-APDU. Returns an instance of an ApduCommand derived class."""
        # first look-up which of our member classes match CLA + INS
        a_cls = self.lookup(apdu.ins, apdu.cla)
        if not a_cls:
            raise ValueError('Unknown CLA=%02X INS=%02X' % (apdu.cla, apdu.ins))
        # then create an instance of that class and return it
        return a_cls.from_apdu(apdu)

    def parse_cmd_bytes(self, buf:bytes) -> ApduCommand:
        """Parse from a buffer (simtrace style). Returns an instance of an ApduCommand derived class."""
        # first look-up which of our member classes match CLA + INS
        cla = buf[0]
        ins = buf[1]
        a_cls = self.lookup(ins, cla)
        if not a_cls:
            raise ValueError('Unknown CLA=%02X INS=%02X' % (cla, ins))
        # then create an instance of that class and return it
        return a_cls.from_bytes(buf)



class ApduHandler(abc.ABC):
    @abc.abstractmethod
    def input(self, cmd: bytes, rsp: bytes):
        pass


class TpduFilter(ApduHandler):
    """The TpduFilter removes the T=0 specific GET_RESPONSE from the TPDU stream and
       calls the ApduHandler only with the actual APDU command and response parts."""
    def __init__(self, apdu_handler: ApduHandler):
        self.apdu_handler = apdu_handler
        self.state = 'INIT'
        self.last_cmd = None

    def input_tpdu(self, tpdu:Tpdu):
        # handle SW=61xx / 6Cxx
        if tpdu.sw[0] == 0x61 or tpdu.sw[0] == 0x6C:
            self.state = 'WAIT_GET_RESPONSE'
            # handle successive 61/6c responses by stupid phone/modem OS
            if tpdu.ins != 0xC0:
                self.last_cmd = tpdu.cmd
            return None
        else:
            if self.last_cmd:
                icmd = self.last_cmd
                self.last_cmd = None
            else:
                icmd = tpdu.cmd
            apdu = Apdu(icmd, tpdu.rsp)
            if self.apdu_handler:
                return self.apdu_handler.input(apdu)
            return Apdu(icmd, tpdu.rsp)

    def input(self, cmd: bytes, rsp: bytes):
        if isinstance(cmd, str):
            cmd = bytes.fromhex(cmd)
        if isinstance(rsp, str):
            rsp = bytes.fromhex(rsp)
        tpdu = Tpdu(cmd, rsp)
        return self.input_tpdu(tpdu)

class ApduDecoder(ApduHandler):
    def __init__(self, cmd_set: ApduCommandSet):
        self.cmd_set = cmd_set

    def input(self, apdu: Apdu):
        return self.cmd_set.parse_cmd_apdu(apdu)


class CardReset:
    def __init__(self, atr: bytes):
        self.atr = atr

    def __str__(self):
        if self.atr:
            return '%s(%s)' % (type(self).__name__, b2h(self.atr))
        return '%s' % (type(self).__name__)
