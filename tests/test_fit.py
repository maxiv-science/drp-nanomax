# flake8: noqa
import logging
import time

import h5py
import numpy
import numpy as np
import pytest
from PyMca5.PyMcaPhysics.xrf.FastXRFLinearFit import FastXRFLinearFit
from PyMca5.PyMcaPhysics.xrf.XRFBatchFitOutput import OutputBuffer

_logger = logging.getLogger(__name__)


class SingleFit(FastXRFLinearFit):
    def __init__(self, mcafit=None):
        super().__init__()

    def prepareMultipleSpectra(
        self,
        x=None,
        y=None,
        xmin=None,
        xmax=None,
        configuration=None,
        concentrations=False,
        ysum=None,
        weight=None,
        refit=True,
        livetime=None,
        outbuffer=None,
        save=True,
        **outbufferinitargs
    ):
        """
        This method performs the actual fit. The y keyword is the only mandatory input argument.

        :param x: 1D array containing the x axis (usually the channels) of the spectra.
        :param y: nD array containing the spectra
        :param xmin: lower limit of the fitting region
        :param xmax: upper limit of the fitting region
        :param ysum: sum spectrum
        :param weight: 0 Means no weight, 1 Use an average weight, 2 Individual weights (slow)
        :param concentrations: 0 Means no calculation, 1 Calculate elemental concentrations
        :param refit: if False, no check for negative results. Default is True.
        :param livetime: It will be used if not different from None and concentrations
                         are to be calculated by using fundamental parameters with
                         automatic time. The default is None.
        :param outbuffer:
        :param save: set to False to postpone saving the in-memory buffers
        :return OutputBuffer: works like a dict
        """
        # Parse data
        x, data, self.mcaIndex, livetime = self._fitParseData(
            x=x, y=y, livetime=livetime
        )

        # Calculation needs buffer for memory allocation (memory or H5)
        t0 = time.time()

        # Configure fit
        nSpectra = data.size // data.shape[self.mcaIndex]
        (
            configorg,
            self.config,
            weight,
            weightPolicy,
            self.autotime,
            self.liveTimeFactor,
        ) = self._fitConfigure(
            configuration=configuration,
            concentrations=concentrations,
            livetime=livetime,
            weight=weight,
            nSpectra=nSpectra,
        )

        outbuffer = {}
        outbuffer["configuration"] = configorg

        # Sum spectrum
        if ysum is None:
            if weightPolicy == 1:
                # we need to calculate the sum spectrum
                # to derive the uncertainties
                sumover = "all"
            elif not concentrations:
                # one spectrum is enough
                sumover = "first pixel"
            else:
                sumover = "first vector"
            yref = self._fitReferenceSpectrum(
                data=data, mcaIndex=self.mcaIndex, sumover=sumover
            )
        else:
            yref = ysum

        # Get the basis of the linear models (i.e. derivative to peak areas)
        if xmin is None:
            xmin = self.config["fit"]["xmin"]
        if xmax is None:
            xmax = self.config["fit"]["xmax"]
        dtypeCalculcation = self._fitDtypeCalculation(data)
        self._mcaTheory.setData(x=x, y=yref, xmin=xmin, xmax=xmax)
        self.derivatives, self.freeNames, nFree, self.nFreeBkg = self._fitCreateModel(
            dtype=dtypeCalculcation
        )

        # Background anchor points (if any)
        self.anchorslist = self._fitBkgAnchorList(config=self.config)

        # MCA trimming: [iXMin:iXMax]
        iXMin, iXMax = self._fitMcaTrimInfo(x=x)
        self.sliceChan = slice(iXMin, iXMax)
        nObs = iXMax - iXMin

        # Least-squares parameters
        if weightPolicy == 2:
            # Individual spectrum weights (assumed Poisson)
            SVD = False
            sigma_b = None
        elif weightPolicy == 1:
            # Average weight from sum spectrum (assume Poisson)
            # the +1 is to prevent misbehavior due to weights less than 1.0
            sigma_b = 1 + numpy.sqrt(yref[self.sliceChan]) / nSpectra
            sigma_b = sigma_b.reshape(-1, 1)
            SVD = True
        else:
            # No weights
            SVD = True
            sigma_b = None
        self.lstsq_kwargs = {"svd": SVD, "sigma_b": sigma_b, "weight": weight}

        # Allocate output buffers
        stackShape = data.shape
        imageShape = list(stackShape)
        imageShape.pop(self.mcaIndex)
        imageShape = tuple(imageShape)
        self.paramShape = (nFree,) + imageShape
        self.dtypeResult = self._fitDtypeResult(data)
        dataAttrs = {}  # {'units':'counts'})
        paramAttrs = {"errors": "uncertainties", "default": not concentrations}
        fitAttrs = {}
        dataAttrs = {}

        _logger.debug("Configuration elapsed = %f", time.time() - t0)
        t0 = time.time()

    def fitSingleSpectrum(self, data, refit=0, concentrations=0):
        logging.warning("param shape %s", self.paramShape)
        results = np.zeros(self.paramShape, dtype=self.dtypeResult)
        logging.warning("shapeis %s", results.shape)
        uncertainties = np.zeros(self.paramShape, dtype=self.dtypeResult)

        outbuffer = {}
        outbuffer["results"] = results
        outbuffer["uncertainties"] = uncertainties
        outbuffer["labels"] = self.freeNames
        # Fit all spectra
        # logging.warning("members before %s",(self.sliceChan, self.mcaIndex,
        #                self.derivatives,
        #                self.config, self.anchorslist,
        #                self.lstsq_kwargs))
        self._fitLstSqAll(
            data=data,
            sliceChan=self.sliceChan,
            mcaIndex=self.mcaIndex,
            derivatives=self.derivatives,
            fitmodel=None,
            results=results,
            uncertainties=uncertainties,
            config=self.config,
            anchorslist=self.anchorslist,
            lstsq_kwargs=self.lstsq_kwargs,
        )
        # Refit spectra with negative peak areas
        if refit:
            t0 = time.perf_counter()
            self._fitLstSqNegative(
                data=data,
                sliceChan=self.sliceChan,
                mcaIndex=self.mcaIndex,
                derivatives=self.derivatives,
                fitmodel=None,
                results=results,
                uncertainties=uncertainties,
                config=self.config,
                anchorslist=self.anchorslist,
                lstsq_kwargs=self.lstsq_kwargs,
                freeNames=self.freeNames,
                nFreeBkg=self.nFreeBkg,
                nFreeParameters=None,
            )
            logging.warning("refit took %f", time.perf_counter() - t0)
        del self.lstsq_kwargs["last_svd"]
        # return
        # Return results as a dictionary

        if concentrations:
            labels, concentrations = self._fitDeriveMassFractions(
                config=self.config,
                nFreeBkg=self.nFreeBkg,
                results=results,
                autotime=self.autotime,
                liveTimeFactor=self.liveTimeFactor,
            )

            outbuffer["massfractions"] = concentrations
            outbuffer["massfractions_labels"] = labels

        # logging.warning("members after %s", (self.sliceChan, self.mcaIndex,
        #                                      self.derivatives,
        #                                      self.config, self.anchorslist,
        #                                      self.lstsq_kwargs))
        return outbuffer

    def _fitLstSqNegative(
        self, data=None, freeNames=None, nFreeBkg=None, results=None, **kwargs
    ):
        """Refit pixels with negative peak areas (remove the parameters from the model)"""
        nFree = len(freeNames)
        iIter = 1
        nIter = 2 * (nFree - nFreeBkg) + iIter
        logging.warning("max iters %d", nIter)
        nIter = 2
        negativePresent = True
        while negativePresent:
            # Pixels with negative peak areas
            negList = []
            for iFree in range(nFreeBkg, nFree):
                negMask = results[iFree] < 0
                nNeg = negMask.sum()
                if nNeg > 0:
                    negList.append((nNeg, iFree, negMask))

            # No refit needed when no negative peak areas
            if not negList:
                negativePresent = False
                continue

            # Set negative peak areas to zero when
            # the maximal iterations is reached
            if iIter > nIter:
                for nNeg, iFree, negMask in negList:
                    results[iFree][negMask] = 0.0
                    _logger.warning(
                        "%d pixels of parameter %s forced to zero",
                        nNeg,
                        freeNames[iFree],
                    )
                continue

            # Bad pixels: use peak area with the most negative values
            negList.sort()
            negList.reverse()
            badParameters = []
            badParameters.append(negList[0][1])
            badMask = negList[0][2]

            # Combine with masks of all other peak areas
            # (unless none of them has negative pixels)
            # This is done to prevent endless loops:
            # if two or more parameters have common negative pixels
            # and one of them remains negative when forcing other one to zero
            for iFree, (nNeg, iFree, negMask) in enumerate(negList):
                if iFree not in badParameters and nNeg:
                    combMask = badMask & negMask
                    if combMask.sum():
                        badParameters.append(iFree)
                        badMask = combMask

            # Fit with a reduced model (skipped parameters are fixed at zero)
            badNames = [freeNames[iFree] for iFree in badParameters]
            nmin = 0.0025 * badMask.size
            _logger.debug(
                "Refit iteration #{}. Fixed to zero: {}".format(iIter, badNames)
            )
            self._fitLstSqReduced(
                data=data,
                mask=badMask,
                skipParams=badParameters,
                skipNames=badNames,
                results=results,
                nmin=nmin,
                **kwargs
            )
            iIter += 1
            logging.warning("iterations %d", iIter)


def test_batch():
    trigger = 300
    fastFit = SingleFit()
    fastFit.setFitConfigurationFile(
        "data/fit_config_scan_000027_0.1_second_some_elements_removed.cfg"
    )

    with h5py.File("data/scan_000008_xspress3.hdf5", "r") as f:
        channel = f["entry/instrument/xspress3/data"][trigger : trigger + 100, 3, :]

    weight = 0
    refit = 1
    concentrations = 1

    config = fastFit.prepareMultipleSpectra(
        y=channel, weight=weight, refit=refit, concentrations=concentrations
    )

    with h5py.File("data/scan_000008_xspress3.hdf5", "r") as f:
        i = 0
        for x in range(0, f["entry/instrument/xspress3/data"].shape[0], 100):
            channel = f["entry/instrument/xspress3/data"][x : x + 100, 3]
            if channel.shape[0] != 100:
                break
            logging.warning("i %s", i)
            i += 1
            res = fastFit.fitSingleSpectrum(
                data=channel, refit=refit, concentrations=concentrations
            )
    # res2 = fastFit.fitSingleSpectrum(data=channel2, refit=refit, concentrations=concentrations)
    result = res


# @pytest.mark.parametrize("trigger", [100,400,523,1109])
def est_seq():
    trigger = 300
    fastFit = SingleFit()
    fastFit.setFitConfigurationFile(
        "data/fit_config_scan_000027_0.1_second_some_elements_removed.cfg"
    )

    with h5py.File("data/scan_000008_xspress3.hdf5", "r") as f:
        channel = f["entry/instrument/xspress3/data"][trigger][3:, :]
        channel2 = f["entry/instrument/xspress3/data"][trigger + 1][3:, :]

    weight = 0
    refit = 1
    concentrations = 1

    config = fastFit.prepareMultipleSpectra(
        y=channel[0], weight=weight, refit=refit, concentrations=concentrations
    )

    with h5py.File("data/scan_000008_xspress3.hdf5", "r") as f:
        i = 0
        for c in f["entry/instrument/xspress3/data"]:
            channel = c[3:]
            logging.warning("i %s", i)
            i += 1
            if i > 10:
                break
            res = fastFit.fitSingleSpectrum(
                data=channel, refit=refit, concentrations=concentrations
            )
    # res2 = fastFit.fitSingleSpectrum(data=channel2, refit=refit, concentrations=concentrations)
    result = res

    logging.warning("massfracs %s", result)

    r = {
        l: v[0] for l, v in zip(result["massfractions_labels"], result["massfractions"])
    }
    logging.warning("massfrac dict %s", r)
    with h5py.File("outputDir/IMAGES.h5", "r") as f:
        for l, v in r.items():
            massfrac = f[
                "/images/xrf_fit/results/massfractions/" + l.replace(" ", "_")
            ][trigger]
            assert np.isclose(v, massfrac)


def est_fit():
    fastFit = FastXRFLinearFit()
    fastFit.setFitConfigurationFile(
        "data/fit_config_scan_000027_0.1_second_some_elements_removed.cfg"
    )

    with h5py.File("data/scan_000008_xspress3.hdf5", "r") as f:
        channel = f["entry/instrument/xspress3/data"][500][3, :]
        channel2 = f["entry/instrument/xspress3/data"][540][3, :]
    # channel = np.zeros((4096,), dtype=np.uint32)
    # res = fastFit.fitMultipleSpectra(
    #
    # )

    # result = res.__dict__
    # del result["_labelFormats"]

    # assert round(result["_buffers"]["massfractions"][5][0],6) == round(3.0883595e-7,6)


def est_fullbatch():
    fastFit = FastXRFLinearFit()
    fastFit.setFitConfigurationFile(
        "data/fit_config_scan_000027_0.1_second_some_elements_removed.cfg"
    )

    outputDir = "outputDir"
    outputRoot = ""
    fileEntry = ""
    fileProcess = ""
    refit = 1
    filepattern = None
    begin = None
    end = None
    increment = None
    backend = None
    weight = 0
    tif = 0
    edf = 0
    csv = 0
    h5 = 1
    dat = 0
    concentrations = 1
    diagnostics = 0
    debug = 0
    multipage = 0
    overwrite = 1

    outbuffer = OutputBuffer(
        outputDir=outputDir,
        outputRoot=outputRoot,
        fileEntry=fileEntry,
        fileProcess=fileProcess,
        diagnostics=diagnostics,
        tif=tif,
        edf=edf,
        csv=csv,
        h5=h5,
        dat=dat,
        multipage=multipage,
        overwrite=overwrite,
    )

    with h5py.File("data/scan_000008_xspress3.hdf5", "r") as f:
        dataStack = f["entry/instrument/xspress3/data"][:, 3]

    with outbuffer.saveContext():
        outbuffer = fastFit.fitMultipleSpectra(
            y=dataStack,
            weight=weight,
            refit=refit,
            concentrations=concentrations,
            outbuffer=outbuffer,
        )


# this test just makes sure that the batch doesn't do magic and fitting one by one give the same result as a batch
@pytest.mark.parametrize("trigger", [100, 400, 523, 1110])
def est_iterative(trigger):
    fastFit = SingleFit()
    fastFit.setFitConfigurationFile(
        "data/fit_config_scan_000027_0.1_second_some_elements_removed.cfg"
    )

    with h5py.File("data/scan_000008_xspress3.hdf5", "r") as f:
        channel = f["entry/instrument/xspress3/data"][trigger][3, :]

    weight = 0
    refit = 1
    concentrations = 1

    res = fastFit.fitMultipleSpectra(
        y=channel, weight=weight, refit=refit, concentrations=concentrations
    )

    result = res.__dict__

    logging.warning("massfracs %s", result["_buffers"])
    logging.warning("massfracs %s", result["_labels"])

    r = {
        l: v[0]
        for l, v in zip(
            result["_labels"]["massfractions"], result["_buffers"]["massfractions"]
        )
    }
    logging.warning("massfrac dict %s", r)
    with h5py.File("outputDir/IMAGES.h5", "r") as f:
        for l, v in r.items():
            massfrac = f[
                "/images/xrf_fit/results/massfractions/" + l.replace(" ", "_")
            ][trigger]
            assert np.isclose(v, massfrac)
