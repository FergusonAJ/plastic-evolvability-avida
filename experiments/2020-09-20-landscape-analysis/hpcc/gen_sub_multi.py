'''
Generate slurm job submission scripts - one per condition
'''

import argparse, os, sys, errno, subprocess, csv
from pyvarco import CombinationCollector

seed_offset = 21000
default_num_replicates = 30
job_time_request = "96:00:00"
job_memory_request = "4G"
job_name = "avida"
executable = "avida"
base_script_filename = './base_script.txt'

# Create combo object to collect all conditions we'll run
combos = CombinationCollector()
combos.register_var('EVENT_FILE_PREFIX')
combos.register_var('SENSORS')
combos.add_val('EVENT_FILE_PREFIX', [\
        'events-ALL-u0',        \
        'events-A-u0',        \
        'events-B-u0',        \
        'events-chg-u3',          \
        'events-chg-u10',          \
        'events-chg-u100',          \
        'events-chg-u300',          \
        'events-chg-u1000'
    ])
combos.add_val('SENSORS', ['0','1'])
combos.add_exception({'EVENT_FILE_PREFIX': 'events-ALL-u0', 'SENSORS' : '0'})
combos.add_exception({'EVENT_FILE_PREFIX': 'events-A-u0', 'SENSORS' : '0'})
combos.add_exception({'EVENT_FILE_PREFIX': 'events-B-u0', 'SENSORS' : '0'})

# Load in the base slurm file
with open(base_script_filename, 'r') as fp:
    base_sub_script = fp.read()

'''
This is functionally equivalent to the mkdir -p [fname] bash command
'''
def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

def main():
    parser = argparse.ArgumentParser(description="Run submission script.")
    parser.add_argument("--phase_one_dir", type=str, help="Where is the output directory for phase one of each run?")
    parser.add_argument("--phase_two_dir", type=str, help="Where is the output directory for phase two of each run?")
    parser.add_argument("--config_dir", type=str, help="Where is the configuration directory for experiment?")
    parser.add_argument("--replicates", type=int, default=default_num_replicates, help="How many replicates should we run of each condition?")
    parser.add_argument("--analysis_file", type=str, default="analysis.cfg", help="Path to the analysis script to use for avida analyze mode.")
    parser.add_argument("--job_dir", type=str, help="Where to output these job files?")

    # Load in command line arguments
    args = parser.parse_args()
    phase_one_dir = args.phase_one_dir
    phase_two_dir = args.phase_two_dir
    config_dir = args.config_dir
    num_replicates = args.replicates
    analysis_file_path = args.analysis_file
    job_dir = args.job_dir
    
    # Get list of all combinations to run
    combo_list = combos.get_combos()    
    # Calculate how many jobs we have, and what the last id will be
    num_jobs = num_replicates * len(combo_list)
    final_job_id = seed_offset + num_jobs
    num_digits = len(str(final_job_id))
    print(f'Generating {num_jobs} across {len(combo_list)} files!')

    # Create job file for each condition
    cur_job_id = 0
    for condition_dict in combo_list:
        cur_seed = seed_offset + (cur_job_id * num_replicates)
        job_id_str = str(cur_seed).zfill(num_digits) 
        filename_prefix = f'{cur_seed}_avida__{combos.get_str(condition_dict)}'
        file_str = base_sub_script
        file_str = file_str.replace("<<TIME_REQUEST>>", job_time_request)
        file_str = file_str.replace("<<ARRAY_ID_RANGE>>", f"1-{num_replicates}")
        file_str = file_str.replace("<<MEMORY_REQUEST>>", job_memory_request)
        file_str = file_str.replace("<<JOB_NAME>>", job_name)
        file_str = file_str.replace("<<CONFIG_DIR>>", config_dir)
        file_str = file_str.replace("<<EXEC>>", executable)
        file_str = file_str.replace("<<JOB_SEED_OFFSET>>", str(cur_seed))

        #### Phase 1
        file_str = file_str.replace("<<PHASE_1_DIR>>", \
            os.path.join(phase_one_dir, f'{filename_prefix}', '${SEED}'))
        # Format configuration parameters for the run
        run_params =  f'-set EVENT_FILE {condition_dict["EVENT_FILE_PREFIX"] + "_phase-one.cfg"}'
        run_params +=  ' -set COPY_MUT_PROB 0.0025'
        run_params += f' -set DISABLE_REACTION_SENSORS {condition_dict["SENSORS"]}' 
        run_params +=  ' -set REACTION_SENSORS_NEUTRAL 0.0'
        run_params +=  ' -set PHYLOGENY_SNAPSHOT_RES 200000'
        run_params +=  ' -set RANDOM_SEED ${SEED}'
        # Add run commands if we're running the experiment.
        run_commands = ''
        run_commands += f'RUN_PARAMS="{run_params}"\n'
        run_commands += 'echo "./${EXEC} ${RUN_PARAMS}" > cmd.log\n'
        run_commands += './${EXEC} ${RUN_PARAMS} > run.log\n'
        run_commands += 'mv ./*.csv ./data/ \n'
        file_str = file_str.replace("<<PHASE_1_RUN_COMMANDS>>", run_commands)
        # Add analysis commands if we're analyzing the data
        analysis_commands = ''
        analysis_commands += f'RUN_PARAMS="{run_params}"\n'
        analysis_commands += './${EXEC} ${RUN_PARAMS}'
        analysis_commands += ' -set ANALYZE_FILE ' + analysis_file_path 
        analysis_commands += ' -a\n'
        file_str = file_str.replace("<<PHASE_1_ANALYSIS_COMMANDS>>", analysis_commands)
        
        #### Phase transition
        transition_commands = ''
        # If we are using sensors, only continue if plasticity is perfect
        if condition_dict['SENSORS'] == '0':
            transition_commands += 'python3 check_plasticity.py\n'
            transition_commands += 'if [ -s is_perfectly_plastic.txt ] \n'
            transition_commands += 'then \n'
            transition_commands += '\tmkdir -p ${PHASE_2_DIR}\n'
            transition_commands += '\tcd ${PHASE_2_DIR}\n'
            transition_commands += '\tcp ${CONFIG_DIR}/*.cfg .\n'
            transition_commands += '\tcp ${CONFIG_DIR}/*.org .\n'
            transition_commands += '\tcp ${CONFIG_DIR}/${EXEC} .\n'
            transition_commands += '\tcp ${PHASE_1_DIR}/data/analysis/env_all/final_dominant.gen ./seed_org.gen\n'
            transition_commands += 'fi \n'
            transition_commands += 'cd ${PHASE_1_DIR}\n'
            transition_commands += 'if [ ! -s is_perfectly_plastic.txt ] \n'
            transition_commands += 'then \n'
            transition_commands += '\techo "Replicate did not reach perfect plasticity!" \n'
            transition_commands += '\texit 0\n'
            transition_commands += 'fi \n'

        else: # Continue regardless of plasticity
            transition_commands += 'mkdir -p ${PHASE_2_DIR}\n'
            transition_commands += 'cd ${PHASE_2_DIR}\n'
            transition_commands += 'cp ${CONFIG_DIR}/*.cfg .\n'
            transition_commands += 'cp ${CONFIG_DIR}/*.org .\n'
            transition_commands += 'cp ${CONFIG_DIR}/${EXEC} .\n'
            transition_commands += 'cp ${PHASE_1_DIR}/data/analysis/env_all/final_dominant.gen ./seed_org.gen\n'
        file_str = file_str.replace('<<PHASE_TRANSITION>>', transition_commands)
        
        #### Phase 2
        file_str = file_str.replace("<<PHASE_2_DIR>>", \
            os.path.join(phase_two_dir, f'{filename_prefix}', '${SEED}'))
        # Format configuration parameters for the run
        run_params =  f'-set EVENT_FILE {condition_dict["EVENT_FILE_PREFIX"] + "_phase-two.cfg"}'
        run_params +=  ' -set COPY_MUT_PROB 0.0025'
        run_params += f' -set DISABLE_REACTION_SENSORS {condition_dict["SENSORS"]}' 
        run_params +=  ' -set REACTION_SENSORS_NEUTRAL 0.0'
        run_params +=  ' -set PHYLOGENY_SNAPSHOT_RES 200000'
        run_params +=  ' -set RANDOM_SEED ${SEED}'
        # Add run commands if we're running the experiment.
        run_commands = ''
        run_commands += f'RUN_PARAMS="{run_params}"\n'
        run_commands += 'echo "./${EXEC} ${RUN_PARAMS}" > cmd.log\n'
        run_commands += './${EXEC} ${RUN_PARAMS} > run.log\n'
        run_commands += 'mv ./*.csv ./data/ \n'
        file_str = file_str.replace("<<PHASE_2_RUN_COMMANDS>>", run_commands)
        # Add analysis commands if we're analyzing the data
        analysis_commands = ''
        analysis_commands += f'RUN_PARAMS="{run_params}"\n'
        analysis_commands += './${EXEC} ${RUN_PARAMS}'
        analysis_commands += ' -set ANALYZE_FILE ' + analysis_file_path 
        analysis_commands += ' -a\n'
        file_str = file_str.replace("<<PHASE_2_ANALYSIS_COMMANDS>>", analysis_commands)

        with open(os.path.join(job_dir, f'{filename_prefix}.sb'), 'w') as fp:
            fp.write(file_str)
        cur_job_id += 1

if __name__ == "__main__":
    main()
