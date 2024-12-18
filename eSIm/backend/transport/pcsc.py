
import argparse
import re
from typing import Optional

from smartcard.CardConnection import CardConnection
from smartcard.CardRequest import CardRequest
from smartcard.Exceptions import NoCardException, CardRequestTimeoutException, CardConnectionException
from smartcard.System import readers
from smartcard.ExclusiveConnectCardConnection import ExclusiveConnectCardConnection

from osmocom.utils import h2i, i2h, Hexstr

from backend.exceptions import NoCardError, ProtocolError, ReaderError
from backend.transport import LinkBase
from backend.utils import ResTuple


class PcscSimLink(LinkBase):
    """ backend: PCSC reader transport link."""
    name = 'PC/SC'

    def __init__(self, opts: argparse.Namespace = argparse.Namespace(pcsc_dev=0), **kwargs):
        super().__init__(**kwargs)
        self._reader = None
        r = readers()
        if opts.pcsc_dev is not None:
            # actual reader index number (integer)
            reader_number = opts.pcsc_dev
            if reader_number >= len(r):
                raise ReaderError('No reader found for number %d' % reader_number)
            self._reader = r[reader_number]
        else:
            # reader regex string
            cre = re.compile(opts.pcsc_regex)
            for reader in r:
                if cre.search(reader.name):
                    self._reader = reader
                    break
            if not self._reader:
                raise ReaderError('No matching reader found for regex %s' % opts.pcsc_regex)

        self._con = self._reader.createConnection()
        if not getattr(opts, "pcsc_shared", False):
            self._con = ExclusiveConnectCardConnection(self._con)

    def __del__(self):
        try:

            self._con.disconnect()
        except:
            pass

    def wait_for_card(self, timeout: Optional[int] = None, newcardonly: bool = False):
        cr = CardRequest(readers=[self._reader],
                         timeout=timeout, newcardonly=newcardonly)
        try:
            cr.waitforcard()
        except CardRequestTimeoutException as exc:
            raise NoCardError() from exc
        self.connect()

    def connect(self):
        try:
            # To avoid leakage of resources, make sure the reader
            # is disconnected
            self.disconnect()

            # Explicitly select T=0 communication protocol
            self._con.connect(CardConnection.T0_protocol)
        except CardConnectionException as exc:
            raise ProtocolError() from exc
        except NoCardException as exc:
            raise NoCardError() from exc

    def get_atr(self) -> Hexstr:
        return self._con.getATR()

    def disconnect(self):
        self._con.disconnect()

    def _reset_card(self):
        self.disconnect()
        self.connect()
        return 1

    def _send_apdu_raw(self, pdu: Hexstr) -> ResTuple:

        apdu = h2i(pdu)

        data, sw1, sw2 = self._con.transmit(apdu)

        sw = [sw1, sw2]

        # Return value
        return i2h(data), i2h(sw)

    def __str__(self) -> str:
        return "PCSC[%s]" % (self._reader)

    @staticmethod
    def argparse_add_reader_args(arg_parser: argparse.ArgumentParser):
        pcsc_group = arg_parser.add_argument_group('PC/SC Reader',
        """Use a PC/SC card reader to talk to the SIM card.  PC/SC is a standard API for how applications
access smart card readers, and is available on a variety of operating systems, such as Microsoft
Windows, MacOS X and Linux.  Most vendors of smart card readers provide drivers that offer a PC/SC
interface, if not even a generic USB CCID driver is used.  You can use a tool like ``pcsc_scan -r``
to obtain a list of readers available on your system. """)
        pcsc_group.add_argument('--pcsc-shared', action='store_true',
                                help='Open PC/SC reaer in SHARED access (default: EXCLUSIVE)')
        dev_group = pcsc_group.add_mutually_exclusive_group()
        dev_group.add_argument('-p', '--pcsc-device', type=int, dest='pcsc_dev', metavar='PCSC', default=None,
                               help='Number of PC/SC reader to use for SIM access')
        dev_group.add_argument('--pcsc-regex', type=str, dest='pcsc_regex', metavar='REGEX', default=None,
                               help='Regex matching PC/SC reader to use for SIM access')
