# Home Assistant integration for Somfy UAI+

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant custom component that provides an integration to the Somfy UAI+.

Currently, this integration doesn't provide any feedback on motor status (position). This is because the current use case for the author requires the use of Somfy keypad devices that seem to interfere with the UAI+ when both are communicating at the same time over the error-prone SDN protocol. This may be fixed in a future release; interested observers who wish to do this themselves may opt to fork this repo and uncomment the lines dealing with motor position fetching in `cover.py`, and possibly also increase the polling update frequency in `coordinator.py`. Alternatively, the author will happily accept a contribution that allows for a toggling of motor status fetching integration-wide or motor-specific alongside a setting for polling frequency.

Note also that all of the functionality in this integration was made possible by trial and error attempting various JSON RPC calls against the UAI+, and Somfy was unwilling to provide any documentation indicating what other calls or parameters might be available. Any contributors who can bring additional insight into the UAI+'s API will be very much appreciated.