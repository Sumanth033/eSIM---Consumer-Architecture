

from osmocom.gsmtap import GsmtapReceiver

from backend.apdu.ts_102_221 import ApduCommands as UiccApduCommands
from backend.apdu.ts_102_222 import ApduCommands as UiccAdmApduCommands
from backend.apdu.ts_31_102 import ApduCommands as UsimApduCommands
from backend.apdu.global_platform import ApduCommands as GpApduCommands

from . import ApduSource, PacketType, CardReset

ApduCommands = UiccApduCommands + UiccAdmApduCommands + UsimApduCommands + GpApduCommands

class GsmtapApduSource(ApduSource):
    """ApduSource for handling GSMTAP-SIM messages received via UDP, such as
    those generated by simtrace2-sniff.  Note that *if* you use IP loopback
    and localhost addresses (which is the default), you will need to start
    this source before starting simtrace2-sniff, as otherwise the latter will
    claim the GSMTAP UDP port.
    """
    def __init__(self, bind_ip:str='127.0.0.1', bind_port:int=4729):
        """Create a UDP socket for receiving GSMTAP-SIM messages.
        Args:
            bind_ip: IP address to which the socket should be bound (default: 127.0.0.1)
            bind_port: UDP port number to which the socket should be bound (default: 4729)
        """
        super().__init__()
        self.gsmtap = GsmtapReceiver(bind_ip, bind_port)

    def read_packet(self) -> PacketType:
        gsmtap_msg, _addr = self.gsmtap.read_packet()
        if gsmtap_msg['type'] != 'sim':
            raise ValueError('Unsupported GSMTAP type %s' % gsmtap_msg['type'])
        sub_type = gsmtap_msg['sub_type']
        if sub_type == 'apdu':
            return ApduCommands.parse_cmd_bytes(gsmtap_msg['body'])
        if sub_type == 'atr':
            # card has been reset
            return CardReset(gsmtap_msg['body'])
        if sub_type in ['pps_req', 'pps_rsp']:
            # simply ignore for now
            pass
        else:
            raise ValueError('Unsupported GSMTAP-SIM sub-type %s' % sub_type)
