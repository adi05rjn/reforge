# Evaluation

## Completed development checks

The initial release passes 23 Python unittest cases on the development Linux host. Tests include an actual loopback HTTP exchange with a fixture server and reject malformed/unauthorised model output. CLI smoke runs exercise capture, diagnostic recording and offline plan generation. No real model weights or Snapdragon laptop were available in this development environment.

## Snapdragon validation to perform

Record laptop/OEM model, Snapdragon SoC, RAM, Linux distribution/version, kernel, Python version, llama.cpp revision, model ID/weight licence, quantisation and inference backend. Establish basic Linux hardware support independently of Reforge.

Run the fixture plan and then a real local-model plan at least ten times. Measure time to first response, total plan latency, peak RSS and validation failure rate. Inspect whether the model meaningfully prioritises the stated workflow and asks useful questions. Compare the deterministic plan and AI ordering without claiming different package correctness: package correctness comes from the same fixed mapping.

Try a second target profile with incompatible architecture/model and verify that hardware-specific records do not appear in model context or selected diagnostic IDs. Test a missing server, invalid JSON and repeat execution into an existing directory. Confirm that no package, desktop setting, driver or kernel has changed.

These results should be published as measurements after testing, not projected as achieved performance. CPU-only local inference is an acceptable first experiment; NPU acceleration is a separate future integration.
