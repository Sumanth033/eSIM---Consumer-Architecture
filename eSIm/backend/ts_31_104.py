
from osmocom.utils import *
from osmocom.tlv import *
from backend.filesystem import *
from backend.ts_31_102 import ADF_USIM
from backend.ts_51_011 import EF_IMSI, EF_AD
import backend.ts_102_221
from backend.ts_102_221 import EF_ARR


class ADF_HPSIM(CardADF):
    def __init__(self, aid='a000000087100A', has_fs=True, name='ADF.HPSIM', fid=None, sfid=None,
                 desc='HPSIM Application'):
        super().__init__(aid=aid, has_fs=has_fs, fid=fid, sfid=sfid, name=name, desc=desc)

        files = [
            EF_ARR(fid='6f06', sfid=0x06),
            EF_IMSI(fid='6f07', sfid=0x07),
            EF_AD(fid='6fad', sfid=0x03),
        ]
        self.add_files(files)
        # add those commands to the general commands of a TransparentEF
        self.shell_commands += [ADF_USIM.AddlShellCommands()]

    def decode_select_response(self, data_hex):
        return backend.ts_102_221.CardProfileUICC.decode_select_response(data_hex)


# TS 31.104 Section 7.1
sw_hpsim = {
    'Security management': {
        '9862': 'Authentication error, incorrect MAC',
    }
}


class CardApplicationHPSIM(CardApplication):
    def __init__(self):
        super().__init__('HPSIM', adf=ADF_HPSIM(), sw=sw_hpsim)
