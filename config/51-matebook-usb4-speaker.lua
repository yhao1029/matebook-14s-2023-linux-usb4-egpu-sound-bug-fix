-- HKFG-XX SN6140: audible speaker output uses the Headphone DAC.
-- The generic UCM Speaker mixer controls a different DAC. Use software
-- gain so desktop/app volume controls attenuate the actual audio stream.
table.insert(alsa_monitor.rules, {
  matches = {{
    { 'device.name', 'equals', 'alsa_card.pci-0000_00_1f.3-platform-skl_hda_dsp_generic' },
  }},
  apply_properties = {
    ['api.alsa.soft-mixer'] = true,
  },
})
