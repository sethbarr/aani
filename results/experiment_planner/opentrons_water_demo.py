"""Water-only layout demonstration; no fungi, compounds or assay execution."""
from opentrons import protocol_api

metadata = {
    "protocolName": "Fungal discovery — WATER ONLY layout demo",
    "description": "One representative plate. Demonstrates placement, not biological testing.",
    "author": "Behaviour chemistry hackathon",
}
requirements = {"robotType": "OT-2", "apiLevel": "2.16"}
PLAN_ID = 'fungal-67f41e49c7ce'
PLATE_ID = 'attine_cultivar-run1-plate1'
DESTINATIONS = ['D2', 'D8', 'E2', 'B1', 'C10', 'E8', 'D5', 'A3', 'F1', 'B10', 'G2', 'F11', 'F10', 'F2', 'D3', 'A8', 'H9', 'B2', 'C8', 'A9', 'A7', 'C2', 'H1', 'G1', 'E5', 'E3', 'G8', 'E11', 'G10', 'C4', 'G3', 'F5', 'C5', 'F4', 'G11', 'F12', 'A4', 'B11', 'A2', 'H7', 'E10', 'E4', 'H4', 'D12', 'A6', 'H10', 'F3', 'C6', 'H12', 'H3', 'E1', 'D9', 'C12', 'F7', 'C11', 'H5', 'E6', 'B4', 'D4', 'A10', 'B6', 'D10', 'E12', 'H8', 'A5', 'H11', 'A12', 'D11', 'F9', 'C9', 'B5', 'H6', 'E9', 'H2', 'D7', 'F6', 'G5', 'D6', 'B12', 'C3', 'E7']


def run(protocol: protocol_api.ProtocolContext) -> None:
    """Place water into the occupied wells of one illustrative plate."""
    tips = protocol.load_labware("opentrons_96_tiprack_300ul", "1")
    reservoir = protocol.load_labware("nest_12_reservoir_15ml", "2")
    plate = protocol.load_labware("nest_96_wellplate_200ul_flat", "3")
    pipette = protocol.load_instrument("p300_single_gen2", "left", tip_racks=[tips])
    water = protocol.define_liquid(name="Water", description="Demo water only", display_color="#25816b")
    reservoir["A1"].load_liquid(liquid=water, volume=6000)
    protocol.comment("WATER ONLY. No biological preparation, incubation or measurement.")
    protocol.comment("Load 6 mL water into reservoir A1. Use the specified labware and pipette.")
    protocol.pause("Confirm water-only deck setup before proceeding.")
    for well in DESTINATIONS:
        pipette.transfer(50, reservoir["A1"], plate[well], new_tip="always")
    protocol.comment("Water layout demo complete. No fungal result was generated.")
