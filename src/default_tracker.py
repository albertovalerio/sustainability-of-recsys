import sys
import os
import copy
import traceback
from codecarbon import EmissionsTracker
from recbole.quick_start import run_recbole
from recbole.quick_start import load_data_and_model
from recbole.utils import get_trainer
from recbole.config import Config
from config.global_config import get_global_config
from config.params_config import get_params, set_param
from utils import create_folders, write_dict_to_csv

config = get_global_config()
config_dict = get_params()
DATASETS = config.get('DATASETS')
MODELS = config.get('MODELS')
LOG_FILE = config.get('LOG_FILE')
RESULT_PATH = config.get('RESULT_PATH')
EMISSIONS_FILE = config.get('EMISSIONS_FILE')
METRICS_FILE = config.get('METRICS_FILE')
PARAMS_FILE = config.get('PARAMS_FILE')


def process(dataset, model):

	# Create directory structure is not already exists
	_saved = copy.deepcopy(config_dict.get('checkpoint_dir'))
	create_folders([dataset], [model], [RESULT_PATH, _saved])

	# Log for the current dataset
	log = open(LOG_FILE, 'a', encoding='utf-8')
	log.write('New experiment session started.')
	proj_name = dataset.upper() + '_' + model.upper() + '_DEFAULT_PARAM'
	print('executing', proj_name)

	# Setup runtime config
	pth = os.path.join(config_dict.get('checkpoint_dir'), dataset, model)
	set_param('checkpoint_dir', pth)
	results_path = os.path.join(RESULT_PATH, dataset, model)

	try:
		# Start tracking emissions
		with EmissionsTracker(
			project_name=proj_name,
			output_file=results_path + EMISSIONS_FILE,
			tracking_mode='process',
			on_csv_write='update'
		) as tracker:
			tracker.start()
			run_recbole(
				model=model,
				dataset=dataset,
				config_dict=config_dict
			)
			tracker.stop()
			codecarbon_results = dict(vars(tracker))

		log_str = 'EXECUTED: ' + proj_name + '\n'
		log.write(log_str)
		log.flush()
		print(log_str)

		# Compute metrics
		model_saved = os.path.join(pth, sorted(os.listdir(pth))[-1])
		config_rec, model_rec, _, train_data, _, test_data = load_data_and_model(model_saved)
		trainer = get_trainer(config_rec['MODEL_TYPE'], config_rec['model'])(config_rec, model_rec)
		trainer.eval_collector.data_collect(train_data)
		metrics = trainer.evaluate(test_data, model_file=model_saved)

		# Save results
		metrics = dict(metrics)
		config = Config(config_dict=config_dict, config_file_list=None)
		full_params = dict(config._get_final_config_dict())
		metrics['run_id'] = codecarbon_results['run_id']
		metrics['project_name'] = proj_name
		full_params['run_id'] = codecarbon_results['run_id']
		full_params['project_name'] = proj_name
		write_dict_to_csv(results_path + METRICS_FILE, metrics)
		write_dict_to_csv(results_path + PARAMS_FILE, full_params)

	except Exception as e:
		print(traceback.format_exc())
		log_str = 'ERROR: ' + proj_name + '. ' + str(e) + '\n'
		log.write(log_str)
		log.flush()
		print(log_str)

	log.flush()
	log.close()


if __name__ == "__main__":
	args = sys.argv[1:]
	if len(args) == 0:
		for dataset in DATASETS:
			for model in MODELS:
				process(dataset, model)
	else:
		keys = [i.split('=')[0].upper()[2:] for i in args]
		values = [i.split('=')[1] for i in args]
		if 'DATASET' in keys and 'MODEL' in keys:
			dataset = values[keys.index('DATASET')]
			model = values[keys.index('MODEL')]
			if dataset not in DATASETS:
				print('WARNING: invalid DATASET value!')
				print('Valid: ', DATASETS)
			elif model not in MODELS:
				print('WARNING: invalid MODEL value!')
				print('Valid: ', MODELS)
			else:
				process(dataset, model)
		else:
			print('WARNING: required arguments are missing!')
			if 'DATASET' not in keys:
				print('MISSING: DATASET=""')
			if 'MODEL' not in keys:
				print('MISSING: MODEL=""')
	sys.exit(0)