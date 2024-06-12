import sys, os, rtmidi, pydirectinput as pdi
from mido      import MidiFile
from time      import sleep, time
from importlib import import_module

FULL_INSTRUMENT_KEYS = ["y", "u", "i", "o", "p", "h", "j", "k", "l", ";", "n", "m", ",", ".", "/"]
SCALE_NOTES = 12

def getAdditionalKeys(baseKeys: list[str]) -> list[str]:
    result = []

    i = 0
    while i < len(baseKeys):
        if i % 7 not in (2, 6):
            result.append(baseKeys[i])

        result.append(baseKeys[i])
        i += 1

    return result

FULL_INSTRUMENT = getAdditionalKeys(FULL_INSTRUMENT_KEYS)
BELLS_AND_DRUMS = getAdditionalKeys(FULL_INSTRUMENT_KEYS[:8])
FOUR_BUTTONS    = getAdditionalKeys(FULL_INSTRUMENT_KEYS[:4])

class Event:
    def __init__(self, type, note, channel, sleep):
        self.type    = type
        self.note    = note
        self.channel = channel
        self.time    = sleep

    def __repr__(self):
        return "[" + str(self.channel) + "] " + self.type + " " + str(self.note) + " sleep: " + str(self.time)
    
class SkyPlayer:
    def __init__(self):
        pdi.PAUSE = 0.025
        self.notes = FULL_INSTRUMENT
        self.dev = rtmidi.RtMidiIn()

    def channelFilter(self, channel):
        return channel

    def readMidi(self, fileName: str) -> list[Event]:
        mid = MidiFile(fileName)

        events = []

        for message in mid:
            if message.type in ("note_on", "note_off"):
                if message.type == "note_on" and message.velocity == 0:
                      type_ = "note_off"
                else: type_ = message.type

                ch = self.channelFilter(message.channel)
                if ch is None:
                    if len(events) != 0:
                        events[-1].time += message.time
                    continue

                events.append(Event(type_, message.note, ch, message.time))
            elif message.type == "end_of_track":
                events.append(Event("", 0, 0, message.time))
                break
            elif len(events) != 0:
                events[-1].time += message.time

        for i in range(len(events) - 1):
            events[i].time = events[i + 1].time
        events.pop(-1)

        return events

    @staticmethod
    def getBasePitch(minNote: int) -> int:
        return ((minNote // SCALE_NOTES) - 1) * SCALE_NOTES # this gives lowest C for played notes
    
    def playNote(self, note: int, basePitch: int):
        pdi.press([self.notes[(note - basePitch) % len(self.notes)]])
    
    def playMidi(self, fileName: str, basePitch: int | None = None) -> None:
        events = self.readMidi(fileName)
        basePitch = SkyPlayer.getBasePitch(min(events, key = lambda e: e.note).note)

        sleep(4)

        for event in events:
            sTime = time()

            if event.type == "note_on":
                self.playNote(event.note, basePitch)
            
            sTime = event.time - (time() - sTime)
            if sTime > 0: sleep(sTime)

    def getDevices(self) -> tuple[list[str], list[int]]:
        names = []
        ids   = []
        for i in range(self.dev.getPortCount()):
            ids.append(i)
            names.append(self.dev.getPortName(i))

        return names, ids

    def playDevice(self, basePitch: int, getPitch: bool = False):
        while True:
            event = self.dev.getMessage(1)
            if event and event.isNoteOn():
                if getPitch: return event.getNoteNumber()
                self.playNote(event.getNoteNumber(), basePitch)

def select(msg: str, opts: list[str]) -> int:
    while True:
        print(msg)
        for i, opt in enumerate(opts):
            print(f"{i + 1}) {opt}")
        
        a = input("> ")
        try: a = int(a)
        except ValueError: pass
        else:
            if 0 < a <= len(opts):
                return a - 1
            
        print("Invalid input.")

if __name__ == "__main__":
    player = SkyPlayer()

    if "--filter" in sys.argv:
        idx = sys.argv.index("--filter")
        sys.argv.pop(idx)
        file = sys.argv.pop(idx)

        module = import_module(file.replace(".py", "").replace(os.sep, "."))

        try:
            tmp = module.channelFilter
        except NameError:
            print("Invalid filter code. Using default.")
        else:
            player.channelFilter = module.channelFilter

        del module

    instr = select("Instrument type", ["Full", "Bells and drums", "Four buttons"])

    match instr:
        case 0:
            player.notes = FULL_INSTRUMENT
        case 1:
            player.notes = BELLS_AND_DRUMS
        case 2:
            player.notes = FOUR_BUTTONS

    if len(sys.argv) >= 2 and sys.argv[1] == "file":
        player.playMidi(sys.argv[2])
    else:
        while True:
            devNames, devIds = player.getDevices()
            if len(devNames) == 0:
                print("No devices available!")
                input("Press enter to retry")
                continue

            player.dev.openPort(devIds[select("Select device", devNames)])
            print("Press the lowest key on your MIDI device")
            basePitch = SkyPlayer.getBasePitch(player.playDevice(0, True))
            print("OK!")

            try:
                player.playDevice(basePitch)
            except KeyboardInterrupt: 
                player.dev.closePort()