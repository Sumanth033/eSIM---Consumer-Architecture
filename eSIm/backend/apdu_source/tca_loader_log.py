


from backend.utils import h2b

from backend.apdu.ts_102_221 import ApduCommands as UiccApduCommands
from backend.apdu.ts_102_222 import ApduCommands as UiccAdmApduCommands
from backend.apdu.ts_31_102 import ApduCommands as UsimApduCommands
from backend.apdu.global_platform import ApduCommands as GpApduCommands

from . import ApduSource, PacketType, CardReset

ApduCommands = UiccApduCommands + UiccAdmApduCommands + UsimApduCommands + GpApduCommands

class TcaLoaderLogApduSource(ApduSource):
    """ApduSource for reading log files created by TCALoader."""
    def __init__(self, filename:str):
        super().__init__()
        self.logfile = open(filename, 'r')

    def read_packet(self) -> PacketType:
        command = None
        response = None
        for line in self.logfile:
            if line.startswith('Command'):
                command = line.split()[1]
                print("Command: '%s'" % command)
                pass
            elif command and line.startswith('Response'):
                response = line.split()[1]
                print("Response: '%s'" % response)
                return ApduCommands.parse_cmd_bytes(h2b(command) + h2b(response))
        raise StopIteration
