# Corrective Roadie fine-tuning comparison

Actual optimizer steps: 30

Manual excerpt templates, not human research labels. Held-out document families are separate from training. Three old probes are exposed regression checks.

Metrics below are citation/cap diagnostics; support and completeness require reading each answer. No improvement claim is made automatically.

```json
{
  "base": {
    "cases": 12,
    "citations": 12,
    "caps": 0
  },
  "tuned": {
    "cases": 12,
    "citations": 12,
    "caps": 0
  }
}
```

## fbf2bfe063aff6a1-source (source)

What does this manual excerpt tell me? Keep every stated condition and precaution, cite it, and give the answer once.

### Evidence

After thevehiclehas been completelystopped, apply the parking brake and shift the transmission lever to  while depressing the brake pedal.

### Base

According to [S1], after the vehicle has been completely stopped, apply the parking brake and shift the transmission lever to “N” while depressing the brake pedal.

### Tuned

From the supplied manual [S1]:

After the vehicle has been completely stopped, apply the parking brake and shift the transmission lever to **while depressing the brake pedal**.

Token caps: base=False, tuned=False

Review: pending.

## 9ea753097690e165-source (source)

Explain the supplied manual instructions. Preserve their preparation, order, labels and precautions; keep the answer focused.

### Evidence

Right hand drive (RHD) vehicle

Left hand drive (LHD) vehicle

Before starting the vehicle, carry the valid intelligent key. Start the engine by following steps below.

1. Put the gear to P (or N) position.
2. Press and hold the brake pedal.
3. Press the ignition switch (push start button).

### Base

To start the vehicle, follow these steps:

1.  Make sure the gear is in P (Park) or N (Neutral) position [S4].
2.  Press and hold the brake pedal [S4].
3.  Press the ignition switch (push-start button) [S4].

### Tuned

From the supplied manual [S4]:

Before starting the vehicle, carry the valid intelligent key. Start the engine by following steps below.

1. Put the gear to P (or N) position.
2. Press and hold the brake pedal.
3. Press the ignition switch (push start button).

Token caps: base=False, tuned=False

Review: pending.

## fa37a6f0e761b6e9-source (source)

Explain the supplied manual instructions. Preserve their preparation, order, labels and precautions; keep the answer focused.

### Evidence

The anti corrosion agent of the engine coolant is an ethylene glycol type. The cylinder head and the water-pump housing are made of aluminium alloy. Change the engine coolant regularly to prevent the corrosion of these parts. Do not replace the coolant with a clear water.

### Base

The manual [S1] states that the engine coolant is an ethylene glycol type, and the cylinder head and water-pump housing are made of aluminium alloy. It’s important to change the engine coolant regularly to prevent corrosion of these parts. You should *never* replace the coolant with just water [S1].

### Tuned

From the supplied manual [S1]:

The anti corrosion agent of the engine coolant is an ethylene glycol type. The cylinder head and the water-pump housing are made of aluminium alloy. Change the engine coolant regularly to prevent the corrosion of these parts. Do not replace the coolant with a clear water.

Token caps: base=False, tuned=False

Review: pending.

## ae8c9f6a2c86f608-source (source)

What does this manual excerpt tell me? Keep every stated condition and precaution, cite it, and give the answer once.

### Evidence

Click the following on the meter instrument display in sequence:

Settings → Alarm Volume, and select your desired volume level.

The alarm volume settings are divided into three levels : High, Medium, Low. The default level is Medium.

After the ignition is turned off, the alarm volume setting information is retained upon restarting the vehicle. If the battery is disconnected, the default setting is restored.

### Base

This manual excerpt tells you that you can adjust the alarm volume in your all-new Saga. [S4] You can select from three levels: High, Medium, or Low. The default level is Medium. The alarm volume setting is retained when you restart the vehicle, but it will revert to the default (Medium) if the battery is disconnected.

### Tuned

From the supplied manual [S4]:

Click the following on the meter instrument display in sequence:

Settings → Alarm Volume, and select your desired volume level.

The alarm volume settings are divided into three levels : High, Medium, Low. The default level is Medium.

After the ignition is turned off, the alarm volume setting information is retained upon restarting the vehicle. If the battery is disconnected, the default setting is restored.

Token caps: base=False, tuned=False

Review: pending.

## e338637244b7a40e-source (source)

What should I know from this manual passage? Include its important conditions without adding other advice.

### Evidence

To prevent a fire when refueling, always turn the engine off. Also, do not smoke or use any flame near the fuel filler.

Never carry any fuel container in your vehicle.

The fuel may leak from the container and may cause an explosion or a fire.

### Base

According to the manual [S2], to prevent a fire when refueling, always turn the engine off. Also, do not smoke or use any flame near the fuel filler. Never carry any fuel container in your vehicle.

### Tuned

From the supplied manual [S2]:

To prevent a fire when refueling, always turn the engine off. Also, do not smoke or use any flame near the fuel filler.

Never carry any fuel container in your vehicle.

The fuel may leak from the container and may cause an explosion or a fire.

Token caps: base=False, tuned=False

Review: pending.

## 02aa3bbd774ba62b-source (source)

What should I know from this manual passage? Include its important conditions without adding other advice.

### Evidence

In the ON position, most electrical appliances such as meter instrument can be operated.

While in ON position, with the intelligent key in the vehicle and the gear is in Park (P) or Neutral (N) position, press and hold the brake pedal while briefly pressing the ignition switch will start the engine.

If the brake pedal is not pressed and the ignition switch is pressed again, the ignition will switch to the OFF position (vehicle power supply turn off).

Leaving the ignition switch in ON position after engine shutdown will drain the battery. Continuous battery drain may prevent you from starting the vehicle.

### Base

Here’s what the manual passage tells you:

*   In the ON position, some electrical appliances can operate [S3].
*   To start the engine, with the intelligent key and the gear in Park (P) or Neutral (N), press and hold the brake pedal while briefly pressing the ignition switch [S3].
*   If you don’t press the brake pedal, the ignition will turn off [S3].
*   Leaving the ignition switch in ON after the engine is off will drain the battery [S3].

### Tuned

From the supplied manual [S3]:

In the ON position, most electrical appliances such as meter instrument can be operated.

While in ON position, with the intelligent key in the vehicle and the gear is in Park (P) or Neutral (N) position, press and hold the brake pedal while briefly pressing the ignition switch will start the engine.

If the brake pedal is not pressed and the ignition switch is pressed again, the ignition will switch to the OFF position (vehicle power supply turn off).

Leaving the ignition switch in ON position after engine shutdown will drain the battery. Continuous battery drain may prevent you from starting the vehicle.

Token caps: base=False, tuned=False

Review: pending.

## aa660b4baf796f84-procedure-gap (procedure-gap)

Give the full component replacement procedure, including removal, installation and testing, based on this warning.

### Evidence

•Turn the defogger switch off when the window is clear, to prevent battery discharge.

• Do not scratch the heater wire at any time.

The front fog lights illuminate with the multicontrol switch turned 1st stage or 2nd stage and with the front fog light switch turned on.

### Base

Based on [S1], the owner’s manual advises to turn off the defogger switch when the window is clear to prevent battery discharge and to avoid scratching the heater wire. It also states that the front fog lights illuminate with the multicontrol switch in the 1st or 2nd stage and the front fog light switch turned on.

However, the document does not provide a procedure for replacing any components. It only contains warnings about specific actions to take or avoid.

### Tuned

From the supplied evidence [S1]:

•Turn the defogger switch off when the window is clear, to prevent battery discharge.

• Do not scratch the heater wire at any time.

The front fog lights illuminate with the multicontrol switch turned 1st stage or 2nd stage and with the front fog light switch turned on.

The supplied evidence does not contain a full component replacement procedure. It only contains warnings.

Token caps: base=False, tuned=False

Review: pending.

## 906f5b75262359e9-procedure-gap (procedure-gap)

Can you explain all the repair stages and why each is needed from this warning?

### Evidence

For safety reasons, do not allow anyone to be in the vehicle being towed.

For an automatic transmission vehicle, be sure to always use a towing dolly.

To tow with rear wheels on ground: Release the parking brake.

### Base

Okay, let’s break down the warning from your Myvi 2005 owner’s manual [S2].

The manual states: “For safety reasons, do not allow anyone to be in the vehicle being towed.” This means that while you’re towing, absolutely no one should be inside the vehicle you’re pulling.

It also says, “For an automatic transmission vehicle, be sure to always use a towing dolly.” This indicates that you must use a towing dolly when towing an automatic transmission vehicle.

Finally, it says, “To tow with rear wheels on ground: Release the parking brake.” This is the procedure for starting the towing process – you need to release the parking brake.

Essentially, these instructions are there to ensure your safety and the safety of others while towing.

### Tuned

From the supplied document [S2]:

For safety reasons, do not allow anyone to be in the vehicle being towed.

For an automatic transmission vehicle, be sure to always use a towing dolly.

To tow with rear wheels on ground: Release the parking brake.

The supplied document does not provide repair stages. It only provides warnings and instructions.

Token caps: base=False, tuned=False

Review: pending.

## 60d276ab11c4ae0e-procedure-gap (procedure-gap)

How would a mechanic remove and replace the component discussed in this excerpt?

### Evidence

Do not drive with the air cleaner element removed. Failure to observe this will cause excessive engine wear.

Do not oil the element. It may reduce the effectiveness of the element.

### Base

According to [S3], do not drive with the air cleaner element removed. To remove and replace it, a mechanic should not oil the element.

### Tuned

From the supplied document [S3]:

Do not drive with the air cleaner element removed. Failure to observe this will cause excessive engine wear.

Do not oil the element. It may reduce the effectiveness of the element.

The supplied document does not provide instructions on how to remove and replace the component. It only provides warnings.

Token caps: base=False, tuned=False

Review: pending.

## b1215c98ab243e4e-specification-gap (specification-gap)

What exact tightening torque should I use for the component discussed here? Use only this excerpt; say if the value is missing.

### Evidence

When the mode of the steering wheel button is switched to control the multimedia unit, press this button to jump to the next valid radio station in the radio interface. Press this button will also play the next picture or video file in the multimedia (or media) interface.

### Base

The excerpt [S4] describes how to use the steering wheel button to change radio stations or play multimedia files. It does not provide any information about tightening torque for any component.

### Tuned

From the supplied excerpt [S4]:

When the mode of the steering wheel button is switched to control the multimedia unit, press this button to jump to the next valid radio station in the radio interface. Press this button will also play the next picture or video file in the multimedia (or media) interface.

The excerpt does not specify any tightening torque values.

Token caps: base=False, tuned=False

Review: pending.

## cbbc0cfc1e061620-specification-gap (specification-gap)

What exact tightening torque should I use for the component discussed here? Use only this excerpt; say if the value is missing.

### Evidence

Answering and hanging up calls can be done via steering wheel control buttons (the multifunction control buttons at the steering wheel).

While the Bluetooth phone function is active:

• Press Phone button on the steering wheel to answer or hang up the call.

• During the call, adjust the call volume by pressing up/down the volume button.

Tap on to the name or contact number to make Bluetooth phone call.

You can answer, hold, reject or hang up via multimedia unit on Bluetooth phone call interface as below:

Call Status Display: Shows real-time call information, including active calls and any calls placed on hold, for clear and easy call management.

### Base

The excerpt does not specify the tightening torque for any component [S2]. It only describes how to answer and handle calls using the steering wheel controls and the multimedia unit.

### Tuned

The supplied excerpt does not contain any information about tightening torque [S2].

Token caps: base=False, tuned=False

Review: pending.

## 0f409b81dc85602a-specification-gap (specification-gap)

What exact tightening torque should I use for the component discussed here? Use only this excerpt; say if the value is missing.

### Evidence

The parking sensor cannot detect the net-shaped obstacles like iron wires, mooring ropes and blocking net.

The parking sensor cannot detect low obstacles like rocks, stones, wood blocks, etc.

• The parking sensor cannot detect vehicle with a high chassis.

The parking sensor cannot detect soft objects like snow, cotton, sponge that can absorb the ultrasonic wave.

The parking sensor cannot detect certain obstacles with irregular shapes, such as pillars, trees, bicycles, angle iron, kerb stones, and corrugated cardboard.

### Base

The excerpt [S1] does not specify the exact tightening torque for any component. It only describes what the parking sensors cannot detect.

### Tuned

From the supplied document [S1]:

The parking sensor cannot detect the net-shaped obstacles like iron wires, mooring ropes and blocking net.

The parking sensor cannot detect low obstacles like rocks, stones, wood blocks, etc.

• The parking sensor cannot detect vehicle with a high chassis.

The parking sensor cannot detect soft objects like snow, cotton, sponge that can absorb the ultrasonic wave.

The parking sensor cannot detect certain obstacles with irregular shapes, such as pillars, trees, bicycles, angle iron, kerb stones, and corrugated cardboard.

There is no information about the exact tightening torque for any component.

Token caps: base=False, tuned=False

Review: pending.

## dev-oil (exposed-regression)

Explain the engine-oil level check in order, preserving the preparation, waiting period and printed labels.

### Evidence

1. Park the vehicle on a level surface.
2. Warm up the engine to operating temperature and stop it.
3. After a few minutes, slowly pull the dipstick out and wipe the oil clean.
4. Reinsert the dipstick as far as it will go.
5. Pull out the dipstick again and check the oil level if it is between "F" and "L" marks.
6. If the engine oil level is too low, add the engine oil. For recommended engine oil, see Section 17.

### Base

Here’s how to check your engine oil level, following the manufacturer’s instructions [S1]:

1.  Park the vehicle on a level surface.
2.  Warm up the engine to operating temperature and stop it.
3.  Wait a few minutes.
4.  Slowly pull out the dipstick and wipe it clean.
5.  Reinsert the dipstick as far as it will go.
6.  Pull out the dipstick again and check if the oil level is between the “F” and “L” marks.
7.  If the oil level is too low, add engine oil as specified in Section 17.

### Tuned

From the supplied evidence [S1]:

1.  Park the vehicle on a level surface.
2.  Warm up the engine to operating temperature and stop it.
3.  After a few minutes, slowly pull the dipstick out and wipe the oil clean.
4.  Reinsert the dipstick as far as it will go.
5.  Pull out the dipstick again and check the oil level if it is between "F" and "L" marks.
6.  If the engine oil level is too low, add the engine oil. For recommended engine oil, see Section 17.

Token caps: base=False, tuned=False

Review: pending.

## dev-no-pin (exposed-regression)

Can I unblock the washer nozzle using a pin?

### Evidence

Please contact an authorised Perodua Service Centre if the nozzle is blocked. Do not try to unblock it using sharp objects, such as a pin. The nozzle may be damaged.

### Base

No, do not use a pin or any sharp object to unblock the nozzle [S1]. If the nozzle is blocked, please contact an authorised Perodua Service Centre.

### Tuned

From the supplied evidence [S1]:

Please contact an authorised Perodua Service Centre if the nozzle is blocked. Do not try to unblock it using sharp objects, such as a pin. The nozzle may be damaged.

Token caps: base=False, tuned=False

Review: pending.

## dev-evidence-gap (exposed-regression)

Explain all brake-pad replacement stages and their purposes.

### Evidence

Do not continue using the worn brake pads. This could reduce braking effectiveness and cause an accident. Have the brake pads and rotor checked or replaced immediately.

### Base

Okay, let’s talk about replacing your brake pads. [S1] states that you should have your brake pads and rotors checked or replaced immediately if you’re using worn brake pads. This is because worn pads reduce braking effectiveness and can lead to accidents.

Here’s what’s involved in the process, according to the manufacturer:

1.  **Inspection:** Have the brake pads and rotors checked [S1].
2.  **Replacement:** Replace the brake pads and rotors [S1].

That’s all the information provided. It’s important to have a qualified mechanic perform this work to ensure it’s done correctly and safely.

### Tuned

From the supplied evidence, the manufacturer excerpt [S1] states:

Do not continue using the worn brake pads. This could reduce braking effectiveness and cause an accident. Have the brake pads and rotor checked or replaced immediately.

The excerpt does not provide a detailed explanation of the stages involved in brake-pad replacement. It only advises that the brake pads and rotor should be checked or replaced immediately.

Token caps: base=False, tuned=False

Review: pending.