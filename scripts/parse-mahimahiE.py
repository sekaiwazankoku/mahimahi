import json
import os
import argparse
import pprint
from typing import Any, Dict
import matplotlib

import numpy as np
import pandas as pd

from common import MSEC_PER_SEC, ONE_PKT_PER_MS_MBPS_RATE, PKT_TO_WIRE, WIRE, plot_df, parse_exp, plot_multi_exp, try_except_wrapper, CCA_RENAME, ENTRY_NUMBER

import matplotlib.pyplot as plt

from pubplot import Document
from plot_config.figure_type_creator import FigureTypeCreator as FTC

ftc = FTC(paper_use_small_font=True, use_markers=False)
doc: Document = ftc.get_figure_type()
ppt: Document = FTC(pub_type='presentation', use_markers=False).get_figure_type()

# New Event Names for Attack Log Parsing
EVENT_NAME = {
    '#': 'LOST_OPPORTUNITY',
    '-': 'DEPARTURE',
    '+': 'ARRIVAL',
    'd': 'DROP',
    't': 'INST_TBF',
    'c': 'CUM_TBF',
    'STATE_CHANGE': 'STATE_CHANGE',
    'DELAY_CALCULATED': 'DELAY_CALCULATED'
}

PKT_SIZE = 1504


class NumpyEncoder(json.JSONEncoder):
    """ Custom encoder for numpy data types """
    def default(self, obj):
        if isinstance(obj, (np.int_, np.intc, np.intp, np.int8,
                            np.int16, np.int32, np.int64, np.uint8,
                            np.uint16, np.uint32, np.uint64)):
            
            return int(obj)
        
        elif isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
            return float(obj)
        
        elif isinstance(obj, (np.complex_, np.complex64, np.complex128)):
            return {'real': obj.real, 'imag': obj.imag}
        
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        
        elif isinstance(obj, (np.bool_)):
            return bool(obj)
        
        elif isinstance(obj, (np.void)):
            return None
        
        return json.JSONEncoder.default(self, obj)


class MahimahiLog:

    fpath: str
    df: pd.DataFrame
    summary: Dict[str, Any] = {}

    arrival_df: pd.DataFrame
    drop_df: pd.DataFrame
    departure_df: pd.DataFrame
    queue_df: pd.DataFrame
    attack_log_df: pd.DataFrame  # For attack logs

    def __init__(self, fpath, summary_only=False):
        self.fpath = fpath
        self.exp = parse_exp(os.path.basename(fpath).removesuffix('.log'))
        ret = self.check_cache()
        if(not ret or not summary_only):
            self.parse_mahimahi_log()
            self.derive_metrics()
            self.derive_summary_metrics()
        if(not ret):
            self.write_cache()

    def check_cache(self):
        summary_path = self.fpath.removesuffix('.log') + '.summary'
        if (os.path.exists(summary_path)):
            with open(summary_path, 'r') as f:
                jdict = json.load(f)
            self.summary = jdict
            return True
        return False

    def write_cache(self):
        summary_path = self.fpath.removesuffix('.log') + '.summary'
        with open(summary_path, 'w') as f:
            json.dump(self.summary, f, indent=4, sort_keys=True,
                      separators=(', ', ': '), ensure_ascii=False,
                      cls=NumpyEncoder)

    def parse_mahimahi_log(self):
        with open(self.fpath, 'r') as f:
            lines = f.read().split('\n')

        base_timestamp = None
        queue_size_bytes = None
        records = []

        attack_log_records = []  # Separate storage for attack logs

        for line in lines:
            # Parse headers
            if(line.startswith('#')):
                if(line.startswith('# base timestamp: ')):
                    base_timestamp = int(line.removeprefix('# base timestamp: '))
                if(line.startswith('# queue: droptail [bytes=')):
                    queue_size_bytes = \
                            int(line
                            .removeprefix('# queue: droptail [bytes=')
                            .removesuffix(']'))

            elif(line in [' ', '']):
                pass

            else:
                # Parse Attack Log (STATE_CHANGE or DELAY_CALCULATED)
                if "STATE_CHANGE" in line or "DELAY_CALCULATED" in line:
                    splits = line.split(" ")
                    event = EVENT_NAME.get(splits[1], "UNKNOWN")
                    record = {
                        'time': int(splits[0]) - base_timestamp,
                        'event': event,
                        'value': splits[2]  # value could be state or delay
                    }
                    attack_log_records.append(record)
                    
                else:
                    # Other events (ARRIVAL, DEPARTURE, etc.)
                    splits = line.split(' ')
                    event = EVENT_NAME[splits[1]]
                    assert base_timestamp is not None
                    record = {
                        'time': int(splits[0]) - base_timestamp,
                        'event': event
                    }
                    if(event in ['LOST_OPPORTUNITY', 'ARRIVAL', 'DEPARTURE']):
                        record['bytes'] = int(splits[2])
                    elif(event == 'DROP'):
                        record['bytes'] = int(splits[3])
                    if(event == 'DEPARTURE'):
                        record['delay'] = int(splits[3])
                    records.append(record)

        df = pd.DataFrame(records)
        attack_log_df = pd.DataFrame(attack_log_records)  # Separate attack log DataFrame

        self.df = df
        self.attack_log_df = attack_log_df  # Store attack log DataFrame

        assert base_timestamp is not None
        assert queue_size_bytes is not None

        self.summary.update({
            'base_timestamp': base_timestamp,
            'queue_size_bytes': queue_size_bytes,
            'mm_trace_time_ms': df['time'].max() - df['time'].min()
        })

    def derive_metrics(self):
        df = self.df
        attack_log_df = self.attack_log_df

        # Usual Metrics
        start = df['time'].min()
        end = df['time'].max()

        arrival_df = df[df['event'] == 'ARRIVAL'].groupby('time').sum(numeric_only=True).reindex(range(start, end+1)).fillna(0)
        drop_df = df[df['event'] == 'DROP'].groupby('time').sum(numeric_only=True).reindex(range(start, end+1)).fillna(0)
        departure_df = df[df['event'] == 'DEPARTURE'].groupby('time').sum().reindex(range(start, end+1)).fillna(0)

        self.arrival_df = arrival_df.reset_index()
        self.drop_df = drop_df.reset_index()
        self.departure_df = departure_df.reset_index()

        # Process attack log events
        if not attack_log_df.empty:
            self.process_attack_logs(attack_log_df)

    def process_attack_logs(self, attack_log_df):
        # Example: You can add processing logic for attack logs here (optional)
        state_changes = attack_log_df[attack_log_df['event'] == 'STATE_CHANGE']
        delays = attack_log_df[attack_log_df['event'] == 'DELAY_CALCULATED']

        # You can store them separately or integrate them into the summary
        self.summary['state_changes'] = state_changes['value'].tolist()
        self.summary['calculated_delays'] = delays['value'].tolist()

        # Plotting, summarizing, or other processing will be added below

    # The rest of the class stays the same...
