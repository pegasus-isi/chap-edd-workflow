#!/usr/bin/env python3
##!/usr/bin/python3

'''
Sample Pegasus workflow for running an EDD workflow as part of the
CHESS Analysis Pipelines (CHAP)
https://github.com/keara-soloway/CHAPBookWorkflows
'''

import argparse
import logging
import os
import shutil
import sys

from Pegasus.api import *

logging.basicConfig(level=logging.DEBUG)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# need to know where Pegasus is installed for notifications
PEGASUS_HOME = shutil.which('pegasus-version')
PEGASUS_HOME = os.path.dirname(os.path.dirname(PEGASUS_HOME))

def generate_wf():
    '''
    Main function that parses arguments and generates the pegasus
    workflow
    '''

    parser = argparse.ArgumentParser(description="generate a CHAP edd workflow")
    args = parser.parse_args(sys.argv[1:])
    
    wf = Workflow('chap-edd')
    tc = TransformationCatalog()
    rc = ReplicaCatalog()
    
    # --- Properties ----------------------------------------------------------
    
    # set the concurrency limit for the download jobs, and send some extra usage
    # data to the Pegasus developers
    props = Properties()
    props['pegasus.catalog.workflow.amqp.url'] = 'amqp://friend:donatedata@msgs.pegasus.isi.edu:5672/prod/workflows'
    #props['pegasus.data.configuration'] = 'nonsharedfs'
    props.write() 
    
    # --- Event Hooks ---------------------------------------------------------

    # get emails on all events at the workflow level
    wf.add_shell_hook(EventType.ALL, '{}/share/pegasus/notification/email'.format(PEGASUS_HOME))
    
    # --- Transformations -----------------------------------------------------
    
    container = Container(
                   'chap',
                   Container.SINGULARITY,
                   'http://data.isi.edu/chess/images/chap.sif',
                   image_site="nonlocal"
                )
    tc.add_containers(container)

    chap_wrapper = Transformation(
        'chap_wrapper',
        site='local',
        container=container,
        pfn=BASE_DIR + '/executables/chap_wrapper.sh',
        is_stageable=True
    )
    tc.add_transformations(chap_wrapper)

    # --- Site Catalog -------------------------------------------------
    sc = SiteCatalog()

    # add a local site with an optional job env file to use for compute jobs
    shared_scratch_dir = "{}/work".format(BASE_DIR)
    local_storage_dir = "{}/storage".format(BASE_DIR)
    local = Site("local") \
        .add_directories(
        Directory(Directory.SHARED_SCRATCH, shared_scratch_dir)
            .add_file_servers(FileServer("file://" + shared_scratch_dir, Operation.ALL)),
        Directory(Directory.LOCAL_STORAGE, local_storage_dir)
            .add_file_servers(FileServer("file://" + local_storage_dir, Operation.ALL)))


    sc.add_sites(local)

    # --- Workflow -----------------------------------------------------
    # track the yaml files for the chess wrapper that are required for each job
    executables_dir = os.path.join(BASE_DIR, "executables")
    input_dir = os.path.join(BASE_DIR, "input")
    calibrate_detector_yaml = File("calibrate_detector.yaml")
    rc.add_replica('local', calibrate_detector_yaml, os.path.join(executables_dir, calibrate_detector_yaml.lfn))
    diffraction_volume_yaml = File("diffraction_volume.yaml")
    rc.add_replica('local', diffraction_volume_yaml, os.path.join(executables_dir, diffraction_volume_yaml.lfn))
    microstrain_maps_yaml = File("microstrain_maps.yaml")
    rc.add_replica('local', microstrain_maps_yaml, os.path.join(executables_dir, microstrain_maps_yaml.lfn))

    # other files from the input directory
    ceria_calibration_yaml = File("ceria_calibration.yaml")
    rc.add_replica('local', ceria_calibration_yaml, os.path.join(input_dir, ceria_calibration_yaml.lfn))
    dvl_yaml = File("dvl.yaml")
    rc.add_replica('local', dvl_yaml, os.path.join(input_dir, dvl_yaml.lfn))
    strain_analysis_yaml = File("strain_analysis.yaml")
    rc.add_replica('local', strain_analysis_yaml, os.path.join(input_dir, strain_analysis_yaml.lfn))

    # common input data.tar file
    data_tar = File("data.tar")
    rc.add_replica('local', data_tar, os.path.join(input_dir, data_tar.lfn))

    # calibrate detector job
    ceria_calibrated = File("ceria_calibrated.yaml")
    calibrate_detector_job = Job('chap_wrapper', node_label="calibrate_detector")
    calibrate_detector_job.add_args(calibrate_detector_yaml)
    calibrate_detector_job.add_inputs(data_tar, calibrate_detector_yaml, ceria_calibration_yaml)
    calibrate_detector_job.add_outputs(ceria_calibrated)
    for output in ['mca1_calibration_fit_mask_hkls.png', 'mca1_calibration_tth_initial_guess.png']:
        calibrate_detector_job.add_outputs(File(output), stage_out=True)
    wf.add_jobs(calibrate_detector_job)

    # diffraction volume job
    dvl_measured = File("dvl_measured.yaml")
    diffraction_volume_job = Job('chap_wrapper', node_label="diffraction_volume")
    diffraction_volume_job.add_args(diffraction_volume_yaml)
    diffraction_volume_job.add_inputs(data_tar, diffraction_volume_yaml, dvl_yaml)
    diffraction_volume_job.add_outputs(dvl_measured)
    for output in ['mca1_dvl.png', 'mca1_dvl_mask.png']:
        calibrate_detector_job.add_outputs(File(output), stage_out=True)
    wf.add_jobs(diffraction_volume_job)

    # the microstrain_maps job
    microstrain_maps_job = Job('chap_wrapper', node_label="microstrain_maps")
    microstrain_maps_job.add_args(microstrain_maps_yaml)
    microstrain_maps_job.add_inputs(data_tar, microstrain_maps_yaml, strain_analysis_yaml, ceria_calibrated)
    for output in ['strain.nxs', 'mca1_strainanalysis_unconstrained_fits.mp4', 'mca1_strainanalysis_fit_mask_hkls.png',
                   'mca1_strainanalysis_material_config.png']:
        microstrain_maps_job.add_outputs(File(output), stage_out=True)
    wf.add_jobs(microstrain_maps_job)

    try:
        wf.add_transformation_catalog(tc)
        wf.add_site_catalog(sc)
        wf.add_replica_catalog(rc)
        wf.write()
#        wf.plan(staging_sites={"condorpool": "osn"}, sites=["condorpool"], verbose=5, submit=True)
    except PegasusClientError as e:
        print(e.output)


if __name__ == '__main__':
    generate_wf()

