# fakeDomoticz.py
class Domoticz:
    @staticmethod
    def Error(msg): print(f"ERROR: {msg}")
    @staticmethod
    def Log(msg): print(f"LOG: {msg}")
    @staticmethod
    def Debug(msg): print(f"DEBUG: {msg}")
    @staticmethod
    def Debugging(level): pass
    class Device:
        def __init__(self, Name, Unit, TypeName, Type, Subtype, Options, Used):
            self.Name = Name
            self.Unit = Unit
        def Create(self): print(f"Created device: {self.Name}")
        def Update(self, nValue, sValue): print(f"Updated device {self.Name}: {sValue}")
Devices = {}
Parameters = {
    "Address": "10.0.20.27",
    "Port": "8887",
    "Mode2": "14",
    "Mode3": "1",
    "Mode1": '[{"name": "Test", "voltage": 230, "pf": 0.75}]',
    "Mode6": "Debug"
}
