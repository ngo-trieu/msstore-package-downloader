"""
soap_templates.py
─────────────────
SOAP XML envelope templates cho giao thức MS-WUSP (Windows Update Services Protocol).
Đây là giao thức mà Windows Update Agent sử dụng để giao tiếp với Microsoft.

Luồng:  GetCookie ──▶ SyncUpdates ──▶ GetExtendedUpdateInfo2
"""

import uuid
from datetime import datetime, timedelta, timezone

# ═══════════════════════════════════════════════════════════════════════════════
# Bước 1: Lấy Session Cookie từ FE3
# ═══════════════════════════════════════════════════════════════════════════════
GET_COOKIE_SOAP = """\
<Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xmlns:xsd="http://www.w3.org/2001/XMLSchema"
          xmlns="http://www.w3.org/2003/05/soap-envelope">
  <Header>
    <Action d3p1:mustUnderstand="1"
            xmlns:d3p1="http://www.w3.org/2003/05/soap-envelope"
            xmlns="http://www.w3.org/2005/08/addressing">http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService/GetCookie</Action>
    <MessageID xmlns="http://www.w3.org/2005/08/addressing">urn:uuid:{msg_id}</MessageID>
    <To d3p1:mustUnderstand="1"
        xmlns:d3p1="http://www.w3.org/2003/05/soap-envelope"
        xmlns="http://www.w3.org/2005/08/addressing">https://fe3.delivery.mp.microsoft.com/ClientWebService/client.asmx</To>
    <Security d3p1:mustUnderstand="1"
              xmlns:d3p1="http://www.w3.org/2003/05/soap-envelope"
              xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
      <Timestamp xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
        <Created>{created}</Created>
        <Expires>{expires}</Expires>
      </Timestamp>
      <WindowsUpdateTicketsToken d4p1:id="ClientMSA"
                                 xmlns:d4p1="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
                                 xmlns="http://schemas.microsoft.com/msus/2014/10/WindowsUpdateAuthorization">
        <TicketType Name="MSA" Version="1.0" Policy="MBI_SSL">
          <User />
        </TicketType>
      </WindowsUpdateTicketsToken>
    </Security>
  </Header>
  <Body>
    <GetCookie xmlns="http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService">
      <oldCookie>
      </oldCookie>
      <lastChange>2015-10-21T17:01:07.1472913Z</lastChange>
      <currentTime>{created}</currentTime>
      <protocolVersion>1.40</protocolVersion>
    </GetCookie>
  </Body>
</Envelope>"""

# ═══════════════════════════════════════════════════════════════════════════════
# Bước 2: Đồng bộ danh sách cập nhật (SyncUpdates)
# Placeholder:
#   {0} = EncryptedData (cookie)
#   {1} = WuCategoryId
#   {2} = Release type XML (vd: <User /> cho anonymous)
#   {3} = FlightRing
# ═══════════════════════════════════════════════════════════════════════════════
SYNC_UPDATES_SOAP = """\
<s:Envelope
    xmlns:a="http://www.w3.org/2005/08/addressing"
    xmlns:s="http://www.w3.org/2003/05/soap-envelope">
    <s:Header>
        <a:Action s:mustUnderstand="1">http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService/SyncUpdates</a:Action>
        <a:MessageID>urn:uuid:{msg_id}</a:MessageID>
        <a:To s:mustUnderstand="1">https://fe3.delivery.mp.microsoft.com/ClientWebService/client.asmx</a:To>
        <o:Security s:mustUnderstand="1"
            xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
            <Timestamp
                xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
                <Created>{created}</Created>
                <Expires>{expires}</Expires>
            </Timestamp>
            <wuws:WindowsUpdateTicketsToken wsu:id="ClientMSA"
                xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
                xmlns:wuws="http://schemas.microsoft.com/msus/2014/10/WindowsUpdateAuthorization">
                <TicketType Name="MSA" Version="1.0" Policy="MBI_SSL">
                    {2}
                </TicketType>
            </wuws:WindowsUpdateTicketsToken>
        </o:Security>
    </s:Header>
    <s:Body>
        <SyncUpdates
            xmlns="http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService">
            <cookie>
                <Expiration>{cookie_expires}</Expiration>
                <EncryptedData>{0}</EncryptedData>
            </cookie>
            <parameters>
                <ExpressQuery>false</ExpressQuery>
                <InstalledNonLeafUpdateIDs>
                    <int>1</int><int>2</int><int>3</int><int>11</int><int>19</int>
                    <int>544</int><int>549</int><int>2359974</int><int>2359977</int>
                    <int>5169044</int><int>8788830</int><int>23110993</int><int>23110994</int>
                    <int>54341900</int><int>54343656</int><int>59830006</int><int>59830007</int>
                    <int>59830008</int><int>60484010</int><int>62450018</int><int>62450019</int>
                    <int>62450020</int><int>66027979</int><int>66053150</int><int>97657898</int>
                    <int>98822896</int><int>98959022</int><int>98959023</int><int>98959024</int>
                    <int>98959025</int><int>98959026</int><int>104433538</int><int>104900364</int>
                    <int>105489019</int><int>117765322</int><int>129905029</int><int>130040031</int>
                    <int>132387090</int><int>132393049</int><int>133399034</int><int>138537048</int>
                    <int>140377312</int><int>143747671</int><int>158941041</int><int>158941042</int>
                    <int>158941043</int><int>158941044</int><int>159123858</int><int>159130928</int>
                    <int>164836897</int><int>164847386</int><int>164848327</int><int>164852241</int>
                    <int>164852246</int><int>164852252</int><int>164852253</int>
                </InstalledNonLeafUpdateIDs>
                <OtherCachedUpdateIDs>
                    <int>10</int><int>17</int><int>2359977</int><int>5143990</int>
                    <int>5169043</int><int>5169047</int><int>8806526</int><int>9125350</int>
                    <int>9154769</int><int>10809856</int><int>23110995</int><int>23110996</int>
                    <int>23110999</int><int>23111000</int><int>23111001</int><int>23111002</int>
                    <int>23111003</int><int>23111004</int><int>24513870</int><int>28880263</int>
                    <int>30077688</int><int>30486944</int><int>59107045</int><int>59125697</int>
                    <int>59142249</int><int>60466586</int><int>60478936</int><int>66450441</int>
                    <int>66467021</int><int>66479051</int><int>75202978</int><int>77436021</int>
                    <int>77449129</int><int>85159569</int><int>90199702</int><int>90212090</int>
                    <int>96911147</int><int>97110308</int><int>98528428</int><int>98665206</int>
                    <int>98837995</int><int>98842922</int><int>98842977</int><int>98846632</int>
                    <int>98866485</int><int>98874250</int><int>98879075</int><int>98904649</int>
                    <int>98918872</int><int>98945691</int><int>98959458</int><int>98984707</int>
                    <int>100220125</int><int>100238731</int><int>100662329</int>
                </OtherCachedUpdateIDs>
                <SkipSoftwareSync>false</SkipSoftwareSync>
                <NeedTwoGroupOutOfScopeUpdates>true</NeedTwoGroupOutOfScopeUpdates>
                <FilterAppCategoryIds>
                    <CategoryIdentifier>
                        <Id>{1}</Id>
                    </CategoryIdentifier>
                </FilterAppCategoryIds>
                <TreatAppCategoryIdsAsInstalled>true</TreatAppCategoryIdsAsInstalled>
                <AlsoPerformRegularSync>false</AlsoPerformRegularSync>
                <ComputerSpec/>
                <ExtendedUpdateInfoParameters>
                    <XmlUpdateFragmentTypes>
                        <XmlUpdateFragmentType>Extended</XmlUpdateFragmentType>
                    </XmlUpdateFragmentTypes>
                    <Locales>
                        <string>en-US</string>
                        <string>en</string>
                    </Locales>
                </ExtendedUpdateInfoParameters>
                <ClientPreferredLanguages>
                    <string>en-US</string>
                </ClientPreferredLanguages>
                <ProductsParameters>
                    <SyncCurrentVersionOnly>false</SyncCurrentVersionOnly>
                    <DeviceAttributes>BranchReadinessLevel=CB;CurrentBranch=rs_prerelease;OEMModel=Virtual Machine;FlightRing={3};AttrDataVer=21;SystemManufacturer=Microsoft Corporation;InstallLanguage=en-US;OSUILocale=en-US;InstallationType=Client;FlightingBranchName=external;FirmwareVersion=Hyper-V UEFI Release v2.5;SystemProductName=Virtual Machine;OSSkuId=48;FlightContent=Branch;App=WU;OEMName_Uncleaned=Microsoft Corporation;AppVer=10.0.22621.1;OSArchitecture=AMD64;SystemSKU=None;UpdateManagementGroup=2;IsFlightingEnabled=1;IsDeviceRetailDemo=0;TelemetryLevel=3;OSVersion=10.0.22621.1;DeviceFamily=Windows.Desktop;</DeviceAttributes>
                    <CallerAttributes>Interactive=1;IsSeeker=0;</CallerAttributes>
                    <Products/>
                </ProductsParameters>
            </parameters>
        </SyncUpdates>
    </s:Body>
</s:Envelope>"""

# ═══════════════════════════════════════════════════════════════════════════════
# Bước 3: Lấy URL tải trực tiếp (GetExtendedUpdateInfo2)
# Placeholder:
#   {0} = UpdateID (GUID)
#   {1} = RevisionNumber
#   {2} = Release type XML
#   {3} = FlightRing
# ═══════════════════════════════════════════════════════════════════════════════
GET_FILE_URL_SOAP = """\
<s:Envelope
    xmlns:a="http://www.w3.org/2005/08/addressing"
    xmlns:s="http://www.w3.org/2003/05/soap-envelope">
    <s:Header>
        <a:Action s:mustUnderstand="1">http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService/GetExtendedUpdateInfo2</a:Action>
        <a:MessageID>urn:uuid:{msg_id}</a:MessageID>
        <a:To s:mustUnderstand="1">https://fe3.delivery.mp.microsoft.com/ClientWebService/client.asmx/secured</a:To>
        <o:Security s:mustUnderstand="1"
            xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
            <Timestamp
                xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
                <Created>{created}</Created>
                <Expires>{expires}</Expires>
            </Timestamp>
            <wuws:WindowsUpdateTicketsToken wsu:id="ClientMSA"
                xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
                xmlns:wuws="http://schemas.microsoft.com/msus/2014/10/WindowsUpdateAuthorization">
                <TicketType Name="MSA" Version="1.0" Policy="MBI_SSL">
                    {2}
                </TicketType>
            </wuws:WindowsUpdateTicketsToken>
        </o:Security>
    </s:Header>
    <s:Body>
        <GetExtendedUpdateInfo2
            xmlns="http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService">
            <updateIDs>
                <UpdateIdentity>
                    <UpdateID>{0}</UpdateID>
                    <RevisionNumber>{1}</RevisionNumber>
                </UpdateIdentity>
            </updateIDs>
            <infoTypes>
                <XmlUpdateFragmentType>FileUrl</XmlUpdateFragmentType>
                <XmlUpdateFragmentType>FileDecryption</XmlUpdateFragmentType>
            </infoTypes>
            <deviceAttributes>BranchReadinessLevel=CB;CurrentBranch=rs_prerelease;OEMModel=Virtual Machine;FlightRing={3};AttrDataVer=21;SystemManufacturer=Microsoft Corporation;InstallLanguage=en-US;OSUILocale=en-US;InstallationType=Client;FlightingBranchName=external;FirmwareVersion=Hyper-V UEFI Release v2.5;SystemProductName=Virtual Machine;OSSkuId=48;FlightContent=Branch;App=WU;OEMName_Uncleaned=Microsoft Corporation;AppVer=10.0.22621.1;OSArchitecture=AMD64;SystemSKU=None;UpdateManagementGroup=2;IsFlightingEnabled=1;IsDeviceRetailDemo=0;TelemetryLevel=3;OSVersion=10.0.22621.1;DeviceFamily=Windows.Desktop;</deviceAttributes>
        </GetExtendedUpdateInfo2>
    </s:Body>
</s:Envelope>"""

# Mapping Ring UI → FlightRing parameter
RING_MAP = {
    "Retail":          "Retail",
    "Release Preview": "RP",
    "Insider Slow":    "WIS",
    "Insider Fast":    "WIF",
}

# Release type cho anonymous (không đăng nhập MSA)
RELEASE_TYPE_RETAIL = "<User />"


def _utc_envelope_vars() -> tuple[str, str, str, str]:
    """Sinh bộ biến (msg_id, created, expires, cookie_expires) động theo giờ UTC thực."""
    now = datetime.now(timezone.utc)
    created = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    expires = (now + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    cookie_expires = (now + timedelta(days=3650)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(uuid.uuid4()), created, expires, cookie_expires


def build_get_cookie_soap() -> str:
    """Tạo SOAP envelope cho GetCookie với MessageID và Timestamp động."""
    msg_id, created, expires, _ = _utc_envelope_vars()
    return (
        GET_COOKIE_SOAP.replace("{msg_id}", msg_id)
        .replace("{created}", created)
        .replace("{expires}", expires)
    )


def build_sync_updates_soap(
    cookie: str, wu_cat_id: str, release_type: str, flight_ring: str
) -> str:
    """Tạo SOAP envelope cho SyncUpdates với MessageID và Timestamp động."""
    msg_id, created, expires, cookie_expires = _utc_envelope_vars()
    return (
        SYNC_UPDATES_SOAP.replace("{msg_id}", msg_id)
        .replace("{created}", created)
        .replace("{expires}", expires)
        .replace("{cookie_expires}", cookie_expires)
        .replace("{0}", cookie)
        .replace("{1}", wu_cat_id)
        .replace("{2}", release_type)
        .replace("{3}", flight_ring)
    )


def build_get_file_url_soap(
    update_id: str, revision: str, release_type: str, flight_ring: str
) -> str:
    """Tạo SOAP envelope cho GetExtendedUpdateInfo2 với MessageID và Timestamp động."""
    msg_id, created, expires, _ = _utc_envelope_vars()
    return (
        GET_FILE_URL_SOAP.replace("{msg_id}", msg_id)
        .replace("{created}", created)
        .replace("{expires}", expires)
        .replace("{0}", update_id)
        .replace("{1}", revision)
        .replace("{2}", release_type)
        .replace("{3}", flight_ring)
    )

