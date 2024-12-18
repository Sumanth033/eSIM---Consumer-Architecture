from construct import GreedyBytes, GreedyString
from osmocom.tlv import *
from osmocom.construct import *

# Table 91 + Section 8.2.1.2
class ApplicationId(BER_TLV_IE, tag=0x4f):
    _construct = GreedyBytes

# Table 91
class ApplicationLabel(BER_TLV_IE, tag=0x50):
    _construct = GreedyBytes

# Table 91 + Section 5.3.1.2
class FileReference(BER_TLV_IE, tag=0x51):
    _construct = GreedyBytes

# Table 91
class CommandApdu(BER_TLV_IE, tag=0x52):
    _construct = GreedyBytes

# Table 91
class DiscretionaryData(BER_TLV_IE, tag=0x53):
    _construct = GreedyBytes

# Table 91
class DiscretionaryTemplate(BER_TLV_IE, tag=0x73):
    _construct = GreedyBytes

# Table 91 + RFC1738 / RFC2396
class URL(BER_TLV_IE, tag=0x5f50):
    _construct = GreedyString('ascii')

# Table 91
class ApplicationRelatedDOSet(BER_TLV_IE, tag=0x61):
    _construct = GreedyBytes

# Section 8.2.1.3 Application Template
class ApplicationTemplate(BER_TLV_IE, tag=0x61, nested=[ApplicationId, ApplicationLabel, FileReference,
                          CommandApdu, DiscretionaryData, DiscretionaryTemplate, URL,
                          ApplicationRelatedDOSet]):
    pass
