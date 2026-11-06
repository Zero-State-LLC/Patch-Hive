/**
 * The golden demo rig and one of its patches, for the home page. Copied, not invented: this is
 * what scripts/seed_golden_demo.py writes for fixtures/golden_demo_seed.json (seed 13371337,
 * run fingerprint 7e477143e400). The rig's modules and case come from the seeder's
 * MODULE_FIXTURES and CASE_FIXTURE, placed in fixture order as the seeder places them; the patch
 * is the engine's patch "Offset Gate-Choir", one of the run's 14. Re-copy all of it if the seed,
 * the fixtures or the patch engine change.
 */
import type { RailPatch } from "@/components/PatchRail";
import type { RailRack } from "@/components/RigRail";

/** Patches the engine generated for this rig in the seeded run. */
export const DEMO_RUN_PATCH_COUNT = 14;

export const DEMO_RIG: RailRack = {
  name: "Voltage Lab Control Rack",
  case: {
    id: 2001,
    brand: "Intellijel",
    name: "7U Performance Case",
    total_hp: 208,
    rows: 2,
    hp_per_row: [104, 104],
    power_12v_ma: 3000,
    power_neg12v_ma: 1500,
    power_5v_ma: 500,
  },
  modules: [
    {
      id: 1,
      module_id: 1001,
      row_index: 0,
      start_hp: 0,
      module: {
        id: 1001,
        brand: "Mutable Instruments",
        name: "Plaits",
        hp: 12,
        module_type: "VCO",
        power_12v_ma: 70,
        power_neg12v_ma: 5,
      },
    },
    {
      id: 2,
      module_id: 1002,
      row_index: 0,
      start_hp: 12,
      module: {
        id: 1002,
        brand: "Mutable Instruments",
        name: "Ripples",
        hp: 8,
        module_type: "VCF",
        power_12v_ma: 50,
        power_neg12v_ma: 50,
      },
    },
    {
      id: 3,
      module_id: 1003,
      row_index: 0,
      start_hp: 20,
      module: {
        id: 1003,
        brand: "Intellijel",
        name: "Quad VCA",
        hp: 12,
        module_type: "VCA",
        power_12v_ma: 60,
        power_neg12v_ma: 60,
      },
    },
    {
      id: 4,
      module_id: 1004,
      row_index: 0,
      start_hp: 32,
      module: {
        id: 1004,
        brand: "Make Noise",
        name: "Maths",
        hp: 20,
        module_type: "ENV",
        power_12v_ma: 60,
        power_neg12v_ma: 60,
      },
    },
    {
      id: 5,
      module_id: 1005,
      row_index: 0,
      start_hp: 52,
      module: {
        id: 1005,
        brand: "Mutable Instruments",
        name: "Batumi",
        hp: 10,
        module_type: "LFO",
        power_12v_ma: 70,
        power_neg12v_ma: 10,
      },
    },
    {
      id: 6,
      module_id: 1006,
      row_index: 0,
      start_hp: 62,
      module: {
        id: 1006,
        brand: "Make Noise",
        name: "Rene 2",
        hp: 34,
        module_type: "SEQ",
        power_12v_ma: 150,
        power_neg12v_ma: 30,
      },
    },
    {
      id: 7,
      module_id: 1007,
      row_index: 0,
      start_hp: 96,
      module: {
        id: 1007,
        brand: "Intellijel",
        name: "Mixup",
        hp: 6,
        module_type: "MIX",
        power_12v_ma: 40,
        power_neg12v_ma: 40,
      },
    },
    {
      id: 8,
      module_id: 1008,
      row_index: 1,
      start_hp: 0,
      module: {
        id: 1008,
        brand: "Mutable Instruments",
        name: "Clouds",
        hp: 18,
        module_type: "FX",
        power_12v_ma: 100,
        power_neg12v_ma: 20,
      },
    },
    {
      id: 9,
      module_id: 1009,
      row_index: 1,
      start_hp: 18,
      module: {
        id: 1009,
        brand: "Noise Engineering",
        name: "Ataraxic Iteritas",
        hp: 6,
        module_type: "NOISE",
        power_12v_ma: 42,
        power_neg12v_ma: 22,
      },
    },
    {
      id: 10,
      module_id: 1010,
      row_index: 1,
      start_hp: 24,
      module: {
        id: 1010,
        brand: "Doepfer",
        name: "A-110-1",
        hp: 10,
        module_type: "VCO",
        power_12v_ma: 90,
        power_neg12v_ma: 20,
      },
    },
    {
      id: 11,
      module_id: 1011,
      row_index: 1,
      start_hp: 34,
      module: {
        id: 1011,
        brand: "Befaco",
        name: "Even VCO",
        hp: 8,
        module_type: "VCO",
        power_12v_ma: 36,
        power_neg12v_ma: 26,
      },
    },
  ],
};

export const DEMO_PATCH: RailPatch & { description: string } = {
  id: 8,
  name: "Offset Gate-Choir",
  description: "Rene 2 sequences A-110-1",
  connections: [
    {
      from_module_id: 1006,
      from_port: "CV X",
      to_module_id: 1010,
      to_port: "V/Oct",
      cable_type: "cv",
    },
    {
      from_module_id: 1006,
      from_port: "Gate Out",
      to_module_id: 1004,
      to_port: "Trig 1",
      cable_type: "gate",
    },
    {
      from_module_id: 1010,
      from_port: "Audio Out",
      to_module_id: 1002,
      to_port: "In",
      cable_type: "audio",
    },
    {
      from_module_id: 1002,
      from_port: "LP Out",
      to_module_id: 1003,
      to_port: "In 1",
      cable_type: "audio",
    },
    {
      from_module_id: 1004,
      from_port: "Out 1",
      to_module_id: 1003,
      to_port: "CV 1",
      cable_type: "cv",
    },
  ],
};
