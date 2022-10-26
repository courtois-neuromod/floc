import os, glob
import numpy as np
import pandas as pd
import argparse

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


def process_log(log_path):
    log_dict = {}

    with open(log_path) as f:
        lines = f.readlines()
        stim_list = []
        for line in lines:
            if "stimulus: image = '/scratch/neuromod/src/task_stimuli/data/fLoc" in line:
                image_path = line.split(' ')[-1]
                stim_list.append(image_path[1:-2])
            elif "task - <class 'src.tasks.localizers.FLoc'>" in line:
                taskname = line.split(':')[-2][1:]
                if len(stim_list) > 0:
                    log_dict[taskname] = stim_list
                    stim_list = []

    return log_dict


name_dict = {
    'def': {
        'bodies': 'body-xx.jpg',
        'characters': 'word-xx.jpg',
        'faces': 'adult-xx.jpg',
        'objects': 'car-xx.jpg',
        'places': 'house-xx.jpg'
    },
    'alt': {
        'bodies': 'limb-xx.jpg',
        'characters': 'word-xx.jpg',
        'faces': 'adult-xx.jpg',
        'objects': 'instrument-xx.jpg',
        'places': 'corridor-xx.jpg'
    }
}

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


def get_name(row, task_label):
    '''
    Returns image name from image path for pandas DF row
    '''
    im_path = row['image_path']
    if '.git/annex' in im_path:
        cat = row['category']
        return name_dict[task_label][cat]
    else:
        return im_path.split('/')[-1]


def get_cat(row, task_label):
    '''
    Returns image category from image path for pandas DF row
    '''
    im_path = row['image_path']
    if '.git/annex' in im_path:
        cat = row['category']
        return cat_dict[task_label][cat]
    else:
        return im_path.split('/')[-2]


def update_event(source_list, bids_path, out_path):

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
            img_list = log_dict[task]

            df = pd.read_csv(s, sep = '\t')
            df.insert(loc=4, column='task_version', value=task[-3:], allow_duplicates=True)

            # some ugly code to divide and conquer...
            df_stim = df[df['trial_type'] == 'stimuli']
            df_nostim = df[df['trial_type'] != 'stimuli']

            df_stim.insert(loc=1, column='image_path', value=np.array(img_list), allow_duplicates=True)
            sub_cat = df_stim.apply(lambda row: get_cat(row, task[-3:]), axis=1)
            df_stim.insert(loc=7, column='subcategory', value=sub_cat, allow_duplicates=True)
            img_num = df_stim.apply(lambda row: get_name(row, task[-3:]), axis=1)
            df_stim.insert(loc=8, column='image_num', value=img_num, allow_duplicates=True)

            df_nostim.insert(loc=1, column='image_path', value=np.nan, allow_duplicates=True)
            df_nostim.insert(loc=7, column='subcategory', value=np.nan, allow_duplicates=True)
            df_nostim.insert(loc=8, column='image_num', value=np.nan, allow_duplicates=True)

            # probably more elegant ways to merge & re-sort per index...
            df_merged = pd.concat([df_stim, df_nostim], ignore_index=False)
            idx = df_merged.index.tolist()
            df_merged.insert(loc=0, column='temp_idx', value=idx, allow_duplicates=False)
            df_merged.sort_values(by=['temp_idx'], inplace=True)
            df_merged = df_merged.drop(['temp_idx'], axis=1)

            # get run number, to match bold files (run 1 and 2)
            # (a bit of a hack: onset times only match exactly with itself...)
            # I tried using first and last trial categories, but there are problems w that approach
            on_first = df_merged['onset'][0]
            on_last = df_merged['onset'][df_merged.shape[0]-1]
            ev_list = glob.glob(os.path.join(bids_path, sub, ses, '*_task-fLoc_run-*_events.tsv'))
            assert len(ev_list) == 2

            out_names = []
            for ev in ev_list:
                ev_df = pd.read_csv(ev, sep = '\t')
                if ev_df['onset'][0] == on_first and ev_df['onset'][df_merged.shape[0]-1] == on_last:
                    out_names.append(os.path.basename(ev))
            assert len(out_names) == 1

            out_name = os.path.join(out_dir, out_names[0])
            df_merged.to_csv(out_name, sep='\t', header=True, index=False)

        except:
            print('problems with ' + sub + ', ' + ses)


if __name__ == '__main__':

    args = get_arguments()

    source_path = args.source_dir
    bids_path = args.bids_dir
    out_path = args.out_dir

    source_list = sorted(glob.glob(os.path.join(source_path, 'sub-*/ses-0*/*task-floc*events.tsv')))

    update_event(source_list, bids_path, out_path)
