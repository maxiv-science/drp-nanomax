# Nanomax live analyis pipeline

This repository contains the scientific analysis code which is run in dranspose deployed for nanomax.

On push to this repository, a docker image is built and published at

harbor.maxiv.lu.se/daq/dranspose/nanomax-fluorescence:<branch name>

Once the build pipeline is done, "redeploy" the image at
https://k8s.maxiv.lu.se/dashboard/c/c-rf2jn/explorer/apps.deployment
which are called `nanomax-pipeline-reducer` and `nanomax-pipeline-worker`.

## Tango Device

The pipeline has a tango device called `b303a/dranspose/dranspose` e.g. available via taranta at
https://taranta.maxiv.lu.se/nanomax/devices/b303a/dranspose/dranspose/attributes

The state gives a good indicator of the general health of the pipeline. It should he in
* ON (ready for a scan),
* RUNNING
* CLOSE (finished scan) but data still live viewable

The status lists in detail all ingesters and the streams they provide as well as the workers and a reducer.
The minimal statistics are useful to observe progress.

`completedEvents` are the ones which passed the full pipeline. At the end it should match `totalEvents`

`deployedVersions` is helpful to quickly check which pipeline version is running and to make sure that the ingesters have a compatible version.
A good indicator is that the git hash of the versions match. In doubt, redeploy all deployments in the k8s namespace.

### Parameters

The tango device exposes the parameters requested by the analysis script. For scalars and string the value is directly editable.
For BinaryParameters, the tango device accepts a file path and then uploads the content of this file. Limit the size of these files to several MB.

If the parameters changed with a new analysis version, the Tango device must be restarted in astor to make them visible

### Live Mode

For all tango devices which have a `Live` command, the dranspose tango device has a property called `detectors` which is a
json dictionary of stream name and tango device path: e.g.

    {"eiger-1m":"b303a/dia/eiger-1m", "eiger-4m":"b303a/dia/eiger-4m"}

On restart of the dranspose device, boolean attributes prefixed with `live_` allow which detectors should be in live, once running the `Live` command of the dranspose tango device.

This mode might be useful if the analysis has a part for alignment where the strict event formation is not super critical (detectors just run with an internal trigger).

## Available Streams

All streams which should be available need to be configured here:

https://gitlab.maxiv.lu.se/nanomax-beamline/pipelines/deploy-nanomax-pipeline/-/blob/main/deployment-configs/global/values.yaml

in the `ingesters` section.

This repository should deploy on push, but you might lack permission. If so, please contact Scientific Data.
You may also check that the IPs match the real world status.

## Live Viewing

The reducer exposes an H5-rest style interface to the processed data. This is accessible e.g. with `h5pyd`

```python
import h5pyd

f = h5pyd.File("http://nanomax-pipeline-reducer.daq.maxiv.lu.se/")

print(list(f.keys()))
```
From here on, it mostly behaves live a H5 File. Once read, the datasets are cached, so to get the latest data, you need to reopen the file.


A silx based viewer will soon be available which is accepting a path to a dataset:

    HsdsViewer http://nanomax-pipeline-reducer.daq.maxiv.lu.se/ "map/massfractions/W L"

## Development

A possible starting point is the following tutorial on dranspose:
https://dranspo.se/tutorials/analysis/

The worker and reducer may be developed locally by replaying ingester recorded streams.

Provide the classes for the worker and reducer as well as the ingester files.
Optionally parameters may be provided in json or pickle format.

   dranspose replay -w "src.worker:FluorescenceWorker" -r "src.reducer:FluorescenceReducer" -f data/contrast_ingest.pkls data/xspress_ingest.pkls -p ../params.json

This repository enforces formatting rules. To easily check before committing, install `pre-commit` and then run

    pre-commit install

for a git hook.

## Test driven development

Under test, there are several tests against which the analysis code is tested on each push.
You run them with

    pytest tests/test_map.py --log-cli-level=INFO

Some tests are skipped and only run if you provide the `--long` option. They keep the reducer running after the end of a test to manually check the result with a live viewer.


## Running tests in docker

Build the docker image:

    podman build -t drp-nanomax .
    
Then start a container from the newly created image. It also mounts the current directory (this git repo) into the container:

    podman run --rm -it -v ".:/mnt" localhost/drp-nanomax:latest /bin/bash

Inside the container shell, install pytest:

    python -m pip install pytest pytest-cov
    
Then run the tests themselves:

    pytest --cov=src --cov-branch --cov-report term-missing --cov-report html --log-cli-level=INFO
    
As the outside directory is bind mounted, you should be able to change code outside the container and rerun the tests inside.
