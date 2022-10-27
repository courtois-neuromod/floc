import os, glob
import numpy as np
import pandas as pd
import argparse
import datalad.api

'''
Script updates events.tsv files to include the image show for each trial,
and specify which version was ran (default or alternative stimuli).

The script then relabels the events files to match the bold.nii.gz data
(runs labelled as run 1 and run 2, chronologically, rather than with task-flocdef/task-flocalt labels)

Default paths are to be ran on elm
'''

def get_arguments():

    parser = argparse.ArgumentParser(description="Update fLoc events.tsv files to include task version and shown stimuli")
    parser.add_argument('--source_dir', default='/unf/eyetracker/neuromod/floc/sourcedata', type=str, help='absolute path to source dataset')
    parser.add_argument('--bids_dir', default='/data/neuromod/DATA/cneuromod/floc', type=str, help='absolute path to bids dataset')
    parser.add_argument('--out_dir', default='/data/neuromod/temp_marie/floc', type=str, help='absolute path to output directory')
    args = parser.parse_args()

    return args


STIM_PATH='/scratch/neuromod/src/task_stimuli/data/fLoc'

def process_log(log_path):
    log_dict = {}

    with open(log_path) as f:
        lines = f.readlines()
        stim_list = []
        for line in lines:
            if f"stimulus: image = '{STIM_PATH}" in line:
                image_path = os.path.relpath(line.split("'")[1], STIM_PATH)
                stim_list.append(image_path)
            elif "task - <class 'src.tasks.localizers.FLoc'>" in line:
                taskname = line.split(':')[-2][1:]
                if len(stim_list) > 0:
                    log_dict[taskname] = stim_list
                    stim_list = []

    return {k:l for k,l in log_dict.items() if len(l) == 360} #remove interrupted tasks


annex2path={}

cat_dict = {
    'def': {
        'bodies': 'body',
        'characters': 'word',
        'faces': 'adult',
        'objects': 'car',
        'places': 'house'
    },
    'alt': {
        'bodies': 'limb',
        'characters': 'word',
        'faces': 'adult',
        'objects': 'instrument',
        'places': 'corridor'
    }
}

# is only used for a few images which annex key have been changed 
def get_annex_path(im_path, stim_ds):
    global annex2path
    if '.git/annex' in im_path:
        key = im_path.split('/')[-1]
        if key in annex2path:
            im_path = annex2path[key]
        else:
            im_path = annex2path[key] = stim_ds.repo.call_git(['log', '--name-only', '--format=oneline', '-1', '--stat', '-S', im_path.split('/')[-1]]).split('\n')[1]
            print(im_path)
    return im_path
    


def get_name(im_path, task_label, ds):
    '''
    Returns image name from image path for pandas DF row
    '''
    return im_path.split('/')[-1]


def get_cat(im_path, task_label, ds):
    '''
    Returns image category from image path for pandas DF row
    '''
    if '.git/annex' in im_path:
        cat = row['category']
        return cat_dict[task_label][cat]
    else:
        return im_path.split('/')[-2]


def update_event(source_list, bids_path, out_path):
    stim_ds = datalad.api.Dataset(bids_path + '/stimuli')

    global annex2path
    for p in glob.glob(bids_path+'stimuli/stimuli/*/*'):
        if os.path.islink(p):
            annex2path[os.readlink(p).split('/')[-1]] = os.path.relpath(p, bids_path+'/stimuli')
    
    for s in source_list:
        sub, ses, fnum, task, suffix = os.path.basename(s).split('_')

        out_dir = os.path.join(out_path, sub, ses)
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        try:
            log_path = glob.glob(os.path.join(source_path, sub, ses, '*' + fnum + '.log'))
            assert len(log_path) == 1
            log_path = log_path[0]

            log_dict = process_log(log_path)
            if not log_dict:
                continue

            img_list = log_dict[task]
            img_list = [get_annex_path(img, stim_ds) for img in img_list]
            print(img_list)

            df = pd.read_csv(s, sep = '\t')
            df.insert(loc=4, column='task_version', value=task[-3:], allow_duplicates=True)


            df['stim_file'] = df['subcategory'] = df['image_num'] = np.nan
            df.stim_file.loc[df.trial_type=='stimuli'] = img_list
            df.subcategory.loc[df.trial_type=='stimuli'] = [get_cat(img, task[-3:], stim_ds) for img in img_list]
            df.image_num.loc[df.trial_type=='stimuli'] = [get_name(img, task[-3:], stim_ds) for img in img_list]


            # get run number, to match bold files (run 1 and 2)
            # (a bit of a hack: onset times only match exactly with itself...)
            # I tried using first and last trial categories, but there are problems w that approach
            on_first = df['onset'][0]
            on_last = df['onset'][df.shape[0]-1]
            ev_list = glob.glob(os.path.join(bids_path, sub, ses, 'func', '*_task-fLoc_run-*_events.tsv'))
            assert len(ev_list) == 2

            out_names = []
            for ev in ev_list:
                ev_df = pd.read_csv(ev, sep = '\t')
                if len(ev_df) == 0: #empty file, heudiconv generated, failed run
                    continue
                if ev_df['onset'][0] == on_first and ev_df['onset'][df.shape[0]-1] == on_last:
                    out_names.append(os.path.basename(ev))
            assert len(out_names) == 1

            out_name = os.path.join(out_dir, out_names[0])
            df.to_csv(out_name, sep='\t', header=True, index=False)

        except Exception as e:
            print('problems with ' + sub + ', ' + ses)
            print(e)
            import traceback
            print(traceback.format_exc())


if __name__ == '__main__':

    args = get_arguments()

    source_path = args.source_dir
    bids_path = args.bids_dir
    out_path = args.out_dir

    source_list = sorted(glob.glob(os.path.join(source_path, 'sub-*/ses-0*/*task-floc*events.tsv')))

    update_event(source_list, bids_path, out_path)
