import os, glob
import numpy as np
import pandas as pd


def test_ev(ev):
    df = pd.read_csv(ev, sep = '\t')

    # includes at least one keypress (max number?)
    #print('Number of key presses: ' + str(np.sum(df['trial_type'] == 'keypress')))
    if not np.sum(df['trial_type'] == 'keypress') > 0:
        print(ev + ' has no button presses')

    # columns filled
    filled_columns = ['trial_type', 'onset', 'offset', 'block', 'category', 'block_trial',
                      'duration', 'target']
    for col in filled_columns:
        if not col in df.columns.to_list():
            print(ev + ' is missing column ' + col)

    # total trials
    df = df[df['trial_type'] != 'keypress']
    if not df.shape[0] == 366:
        print(ev + ' is missing trials')

    # 6 rest trials per run
    if not (df[df['trial_type'] == 'rest'].shape[0] == 6):
        print(ev + ' is missing rest blocks')

    # for each stimulus: 6 blocks of 12 trials each (72 stimuli)
    cat_list = ['bodies', 'characters', 'faces', 'objects', 'places']
    for cat in cat_list:
        try:
            df_cat = df[df['category'] == cat]
            if not df_cat.shape[0] == 72:
                print(ev + ' is missing ' + cat + ' trials')
            if not len(np.unique(df[df['category'] == 'objects']['block'])) == 6:
                print(ev + ' is missing ' + cat + ' blocks')
        except:
            print(ev + ' is missing ' + cat + ' category')


def test_eventfiles(ev_path):
    '''
    two run files per session
    First run is default  stimuli:
        bodies = body, characters = word, faces = adult, objects = car, places = house, scrambled = scrambled
    First run is alternate stimuli:
        bodies = limb, characters = word, faces = adult, objects = instrument, places = corridor, scrambled = scrambled
    # see https://github.com/courtois-neuromod/floc.stimuli/blob/4415763fc728918c856a174be27fe4ea69abdb6c/config.json
    '''
    ev_list = sorted(glob.glob(os.path.join(ev_path, 'sub-0*/ses-0*/sub-0*_ses-00*_task-fLoc_run-0*_events.tsv')))

    for ev in ev_list:
        test_ev(ev)


def main():
    events_path = '../..'
    test_eventfiles(events_path)
