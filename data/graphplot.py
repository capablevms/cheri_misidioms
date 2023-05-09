#!/usr/bin/python3
import matplotlib
matplotlib.rcParams['pdf.fonttype'] = 42
matplotlib.rcParams['ps.fonttype'] = 42

import matplotlib.pyplot as plt
import numpy as np
import json
import pathlib

import argparse
import sys
import statistics as st
import math

out_formats = ["pdf", "png", "svg"]

# The z-values were copied from the multi-time tool found at 
# Laurie Tratt's [multi-time tool](https://github.com/ltratt/multitime/blob/master/zvals.h)
zval = np.array([ 0.01253347, 0.02506891, 0.03760829, 0.05015358, 0.06270678,
                  0.07526986, 0.08784484, 0.10043372, 0.11303854, 0.12566135,
                  0.13830421, 0.15096922, 0.16365849, 0.17637416, 0.18911843,
                  0.20189348, 0.21470157, 0.22754498, 0.24042603, 0.2533471,
                  0.26631061, 0.27931903, 0.2923749, 0.30548079, 0.31863936,
                  0.33185335, 0.34512553, 0.35845879, 0.37185609, 0.38532047,
                  0.39885507, 0.41246313, 0.42614801, 0.43991317, 0.45376219,
                  0.4676988, 0.48172685, 0.49585035, 0.51007346, 0.52440051,
                  0.53883603, 0.55338472, 0.5680515, 0.58284151, 0.59776013,
                  0.61281299, 0.62800601, 0.64334541, 0.65883769, 0.67448975,
                  0.69030882, 0.70630256, 0.72247905, 0.73884685, 0.75541503,
                  0.77219321, 0.78919165, 0.80642125, 0.82389363, 0.84162123,
                  0.85961736, 0.8778963, 0.89647336, 0.91536509, 0.93458929,
                  0.95416525, 0.97411388, 0.99445788, 1.01522203, 1.03643339,
                  1.05812162, 1.08031934, 1.10306256, 1.12639113, 1.15034938,
                  1.17498679, 1.20035886, 1.22652812, 1.25356544, 1.28155157,
                  1.31057911, 1.34075503, 1.37220381, 1.40507156, 1.43953147,
                  1.47579103, 1.51410189, 1.55477359, 1.59819314, 1.64485363,
                  1.69539771, 1.75068607, 1.81191067, 1.88079361, 1.95996398,
                  2.05374891, 2.17009038, 2.32634787, 2.5758293,] )

y_labels = { "BUS_ACCESS" : ("Bus-Access", "events"),
             "BUS_ACCESS_RD_CTAG" : ("Bus-Access-Ctag", "events"), 
             "CPU_CYCLES" : ("CPU-cycles", "cycles"), 
             "INST_RETIRED": ("Instructions retired", "instrs"), 
             "L1D_CACHE": ("L1-data-cache", "accesses"),
             "L1I_CACHE": ("L1-instr-cache", "accesses"),
             "L2D_CACHE": ("L2-data-cache", "accesses"),
             "LL_CACHE_RD": ("LL-cache Read", "accesses"),
             "LL_CACHE_MISS_RD": ("LL-cache Read Misses", "misses"),
             "MEM_ACCESS": ("Memory access", "accesses"),
             "total-time": ("Total Time", "milli-sec"),
             "rss-kb": ("RSS", "KB"),
             "gc-cycles": ("GC cycles", "cycles"),
             "gc-load": ("GC load", "GC runtime ratio"),
             "gc-time": ("GC time", "milli-sec"), 
}

color_grid = { "total-time" : "cadetblue", 
               "rss-kb" : "moccasin", 
               "INST_RETIRED": "tab:purple",
               "L1D_CACHE" : "lightgreen",
               "L2D_CACHE" : "tomato",
               "L1I_CACHE" : "sandybrown",
               "LL_CACHE_RD": "cornflowerblue",
               "LL_CACHE_MISS_RD": "turquoise",
               "MEM_ACCESS": "thistle",
               } 

m_arch_colors = { "hybrid" : "red", 
                 "purecap" : "green"
                } 



def render(outfile, adjust=None):
    if adjust != None :
        _left, _right, _bottom, _top, _hspace = adjust
        plt.subplots_adjust(left=_left,right=_right,bottom=_bottom,top=_top,hspace=_hspace)

    _suffix = outfile.suffix.lstrip(".")
    assert _suffix.lstrip(".") in out_formats, f"invalid output file ({outfile})format {_suffix.lstrip('.')}. " \
                                                              f"acceptable formats -> {out_formats}"

    plt.draw()
    plt.pause(1)
    #input("<Press Enter to continue>")
    plt.savefig(f"{outfile}",format="pdf")
    plt.close()

def gen_bunched_bar_loc(obj_json, bw=0.5, sw=0.5, offset=0.5, strip_zero=False):
  tick_pos, bar_pos = ([], [ [] for _i in obj_json.keys()])
  num_bins = len(obj_json.keys())  # hybrid + purecap
  tick_labels = list(obj_json["hybrid" if "hybrid" in obj_json else "purecap"].keys())

  # Calculate bar and tick positions
  bin_start = offset
  for idx_i in range(len(tick_labels)):
    data_end = bin_start + ((num_bins)*bw)
    benchmark_end = bin_start + ((num_bins)*bw) + sw
    for _bin in range(num_bins):
      bar_pos[_bin].append(bin_start + (_bin * bw) + bw/2)
    tick_pos.append((data_end + bin_start)/2)
    bin_start = benchmark_end 
  return (tick_labels, tick_pos, bar_pos)



def gen_barchart(data, separate, strip_zero, conf_interval):
  tick_lbl, tick_x, bar_x = gen_bunched_bar_loc(data, bw=0.5, sw=0.5, offset=0.5, strip_zero=strip_zero)

  if separate == None: 
    _fig, _subplots = plt.subplots(nrows=1, ncols=2, sharex=False)
  else: 
    _fig, _subplot = plt.subplots(nrows=1, ncols=1, sharex=False)
    _fig.tight_layout()

    purecap_measure, purecap_err = ([], [])
    hybrid_measure, hybrid_err = ([], [])
    for _bm in data["purecap"].keys(): 
      hybrid_measure += [data["hybrid"][_bm][separate]]
      if 'normalised' not in separate and separate != 'gc-load': 
        mean = st.mean(data["hybrid"][_bm][f'raw-{separate}'])
        std_dev = st.stdev(data["hybrid"][_bm][f'raw-{separate}'])
        confidence = zval[conf_interval] * std_dev / math.sqrt(len(data["hybrid"][_bm][f'raw-{separate}']))
        hybrid_err += [confidence]

      purecap_measure += [data["purecap"][_bm][separate]]
      if 'normalised' not in separate and separate != 'gc-load': 
        mean = st.mean(data["purecap"][_bm][f'raw-{separate}'])
        std_dev = st.stdev(data["purecap"][_bm][f'raw-{separate}'])
        confidence = zval[conf_interval] * std_dev / math.sqrt(len(data["purecap"][_bm][f'raw-{separate}']))
        purecap_err += [confidence]

    if 'normalised' not in separate and separate != 'gc-load': 
      _subplot.bar( bar_x[0] , hybrid_measure, label='morello-hybrid', color='r', \
                    width=0.5, yerr=hybrid_err, capstyle='projecting', capsize=4 )
      _subplot.bar( bar_x[1] , purecap_measure , label='morello-purecap', color='g', \
                    width=0.5, yerr=purecap_err, capstyle='projecting', capsize=4 )
    else:
      _subplot.bar( bar_x[0] , hybrid_measure \
                   , label='morello-hybrid', color='r', width=0.5)
      _subplot.bar( bar_x[1] , purecap_measure \
                   , label='morello-purecap', color='g', width=0.5)

    if separate.startswith('normalised'):
      start_idx = len("normalised-")
      _subplot.set_ylabel( f"Normalised {y_labels[separate[start_idx:]][1]}" )
      _subplot.set_title( f"Normalised {y_labels[separate[start_idx:]][0]}" )
    else :
      _subplot.set_ylabel( y_labels[separate][1] )
      _subplot.set_title(y_labels[separate][0] )

    _subplot.grid(True)

    _subplot.set_xticks(tick_x)
    _subplot.set_xticklabels( tick_lbl , rotation=0.0)
    _subplot.legend(loc=0,ncol=2, fontsize='small')



def plot(plot_type, json_file, out_file, events_set, separate_files, conf_interval=95):
  json_file = pathlib.Path(json_file)  # Ensure conversion to pathlib
  out_file = pathlib.Path(out_file)
  assert plot_type == f"histogram", f"Only histograms are currently supported"
  result_data = None
  with open(json_file, "r") as fd:
    result_data = json.load(fd)

  if separate_files : 
    std_event_list, misc_event_list = events_set
    for _event in std_event_list:
      gen_barchart(result_data, _event, False, conf_interval)
      render(out_file.parent.resolve()/ f"{out_file.stem}_{_event}{out_file.suffix}")

      gen_barchart(result_data, f"normalised-{_event}", False, conf_interval)
      render(out_file.parent.resolve()/ f"{out_file.stem}_normalised-{_event}{out_file.suffix}")

    for _event in misc_event_list:
      gen_barchart(result_data, _event, False, conf_interval)
      render(out_file.parent.resolve()/ f"{out_file.stem}_{_event}{out_file.suffix}")

    #gen_barchart(result_data, "gc-time", False)
    #render(out_file.parent.resolve()/ f"{out_file.stem}_gc-time{out_file.suffix}")

    #gen_barchart(result_data, "normalised-gc-time", False)
    #render(out_file.parent.resolve()/ f"{out_file.stem}_normalised-gc-time{out_file.suffix}")

    #gen_barchart(result_data, "gc-load", False)
    #render(out_file.parent.resolve()/ f"{out_file.stem}_gc-load{out_file.suffix}")

    #gen_barchart(result_data, "normalised-gc-load", False)
    #render(out_file.parent.resolve()/ f"{out_file.stem}_normalised-gc-load{out_file.suffix}")
  else: 
    gen_barchart(result_data, None)
    render(outfile)


class Combined_Graphs:
  def __init__(self, plot_type, json_file, out_file_fmt):
    self.json_file = pathlib.Path(json_file)  # Ensure conversion to pathlib
    self.out_file = pathlib.Path(out_file_fmt)  # Ensure conversion to pathlib
    assert plot_type == f"histogram", f"Only histograms are currently supported"
    self.result_data = self.json_file

  @property
  def result_data(self):
    return self._result_data

  @result_data.setter
  def result_data(self, json_file_name):
    self._resultdata = None
    with open(json_file_name, "r") as fd:
      self._result_data = json.load(fd)

  @property
  def out_file(self):
    return self._outfile

  @out_file.setter
  def out_file(self, filename_base):
    self._outfile = filename_base.parent.resolve()/ f"{filename_base.stem}_combined{filename_base.suffix}"
      
  def combined_normalised_plot(self, events_set, conf_interval=99):
    std_event_list, misc_event_list = events_set
    if "jemalloc" in self.result_data.keys() \
       or "snmalloc" in self.result_data.keys():
      self.gen_multiple_barchart(std_event_list, False, conf_interval)
    else:
      self.gen_barchart(std_event_list, False, conf_interval)
    self.render()


  def render(self, adjust=None):
    if adjust != None :
      _left, _right, _bottom, _top, _hspace = adjust
      plt.subplots_adjust(left=_left,right=_right,bottom=_bottom,top=_top,hspace=_hspace)
    else: 
      plt.tight_layout()
    
    _suffix = self.out_file.suffix.lstrip(".")
    assert _suffix.lstrip(".") in out_formats, f"invalid output file ({self.out_file})format {_suffix.lstrip('.')}. " \
                                                                  f"acceptable formats -> {out_formats}"
    
    plt.draw()
    plt.pause(1)
    input("<Press Enter to continue>")
    print(f"saving to {self.out_file}")
    plt.savefig(f"{self.out_file}",format="pdf")
    plt.close()

  def _norm_conf_interval(self, alloc, bm, evt, confidence=98):
    hybrid_mean = st.mean(self.result_data[alloc]["hybrid"][bm][f"raw-{evt}"]) 
    hybrid_std_dev = st.stdev(self.result_data[alloc]["hybrid"][bm][f"raw-{evt}"]) 
    hybrid_len = len(self.result_data[alloc]["hybrid"][bm][f"raw-{evt}"]) 

    purecap_mean = st.mean(self.result_data[alloc]["purecap"][bm][f"raw-{evt}"]) 
    purecap_std_dev = st.stdev(self.result_data[alloc]["purecap"][bm][f"raw-{evt}"]) 
    purecap_len = len(self.result_data[alloc]["purecap"][bm][f"raw-{evt}"]) 
    assert hybrid_len == purecap_len, f"unequal hybrid-purecap runs for {alloc}, bench-{bm}, event-{evt}"

    #norm_std_dev = math.sqrt((pow(hybrid_std_dev,2) / hybrid_len) \
    #                          + (pow(purecap_std_dev,2) / purecap_len)) 
    norm_std_dev = math.sqrt((pow(hybrid_std_dev/hybrid_mean,2) + pow(purecap_std_dev/purecap_mean,2))) * (purecap_mean/ hybrid_mean)
    return zval[confidence] * norm_std_dev / math.sqrt(hybrid_len)

  def gen_multiple_barchart(self, event_list, strip_zero, conf_interval):
    tick_lbl, tick_x, bar_x = self.gen_bunched_bar_loc(event_list, True,
                                                       bw=0.7, sw=1.5, offset=0.0,
                                                       strip_zero=strip_zero)
    num_allocators = len(self.result_data.keys())
    _fig, _subplot = plt.subplots(nrows=num_allocators, ncols=1, sharex=False)
    _fig.tight_layout()

    benchmarks = [ _bm for _bm in self.result_data["jemalloc"]["purecap"].keys() ]
    perf_count = [ {} for _alloc in range(num_allocators)]

    # Calculate and equalise y-axes for all subplots
    max_ylim = max([ self.result_data[alc]["purecap"][bm][f"normalised-{evt}"] \
                     for alc in self.result_data.keys() \
                       for bm in self.result_data[alc]["purecap"] \
                         for evt in event_list ]) 
    max_norm_err = 0.0

    for idx_i, _alloc in enumerate(self.result_data.keys()):
      for idx_j, evt in enumerate(event_list):
        print(f"alloc - {_alloc}, event - {evt}")
        norm_evt = f"normalised-{evt}"
        norm_err = [ self._norm_conf_interval( _alloc, _bm, evt, conf_interval) for _bm in benchmarks ]
        if max(norm_err) > max_norm_err: 
          max_norm_err = max(norm_err)
        perf_count[idx_i][norm_evt] = [ self.result_data[_alloc]["purecap"][_bm][norm_evt] \
                                        for _bm in benchmarks ]
        _subplot[idx_i].bar( bar_x[idx_j] , perf_count[idx_i][norm_evt],
                             label=norm_evt, color=color_grid[evt] , width=0.7, 
                             yerr=norm_err, capstyle='projecting', capsize=4 )
      _subplot[idx_i].grid(True)
      _subplot[idx_i].set_xticks(tick_x)
      _subplot[idx_i].set_xticklabels( tick_lbl , rotation=0.0, fontsize="x-large")
      _subplot[idx_i].set_ylabel("Normalised (vs hybrid) purecap metrics", fontsize="medium")
      _subplot[idx_i].set_ylim([None, math.ceil(max_ylim + max_norm_err)])
      _subplot[idx_i].legend(loc=0,ncol=2, fontsize='x-large')
      _subplot[idx_i].set_title(_alloc)

  def gen_barchart(self, event_list, strip_zero, conf_interval):
    tick_lbl, tick_x, bar_x = self.gen_bunched_bar_loc(event_list, False,
                                                       bw=0.7, sw=1.5, offset=0.0,
                                                       strip_zero=strip_zero)

    _fig, _subplot = plt.subplots(nrows=1, ncols=1, sharex=False)
    _fig.tight_layout()

    perf_count = {} 
    for idx, evt in enumerate(event_list):
      norm_evt = f"normalised-{evt}"
      perf_count[norm_evt] = [ self.result_data["purecap"][_bm][norm_evt] \
                                for _bm in self.result_data["purecap"].keys() ]
      _subplot.bar( bar_x[idx] , perf_count[norm_evt],
                    label=norm_evt, color=color_grid[evt] , width=0.7)

    _subplot.grid(True)
    _subplot.set_xticks(tick_x)
    _subplot.set_xticklabels( tick_lbl , rotation=0.0, fontsize="x-large")
    _subplot.set_ylabel("Normalised (vs hybrid) purecap allocator metrics", fontsize="large")
    _subplot.legend(loc=0,ncol=2, fontsize='x-large')

  def gen_bunched_bar_loc(self, event_list, multichart, bw=0.5, sw=0.5, offset=0.1, strip_zero=False):
    num_bins = len(event_list)
    tick_pos, bar_pos = ([], [ [] for _i in event_list ])
    tick_labels = [ _bm for _bm in self.result_data["jemalloc"]["purecap"].keys()] \
                    if multichart else [ _bm for _bm in self.result_data["purecap"].keys()]

    # Calculate bar and tick positions
    bin_start = offset
    for idx_i in range(len(tick_labels)):
      data_end = bin_start + ((num_bins)*bw)
      benchmark_end = bin_start + ((num_bins)*bw) + sw
      for _bin in range(num_bins):
        bar_pos[_bin].append(bin_start + (_bin * bw) + bw/2)
      tick_pos.append((data_end + bin_start)/2)
      bin_start = benchmark_end 

    return (tick_labels, tick_pos, bar_pos)


class GeoMean_Allocators:
  def __init__(self, plot_type, json_file, out_file_fmt, events):
    self.json_file = pathlib.Path(json_file)  # Ensure conversion to pathlib
    self.out_file = pathlib.Path(out_file_fmt)  # Ensure conversion to pathlib
    assert plot_type == f"histogram", f"Only histograms are currently supported"
    self.result_data = self.json_file
    self._prune_results()
    self.events = events
    self.normal_time =  self._normalise_results()

  @property
  def result_data(self):
    return self._resultdata

  @result_data.setter
  def result_data(self, json_file_name):
    self._resultdata = None
    with open(json_file_name, "r") as fd:
      self._resultdata = json.load(fd)

  @property
  def normal_time(self):
    return self._normaltime

  @normal_time.setter
  def normal_time(self, json_data):
    self._normaltime = json_data

  @property
  def out_file(self):
    return self._outfile

  @out_file.setter
  def out_file(self, filename_base):
    self._outfile = filename_base.parent.resolve()/ f"{filename_base.stem}_alloctime{filename_base.suffix}"

  def _prune_results(self):
    for lib in [ _libs for _libs in self.result_data.keys()]:
      for bm in [ _bm for _bm in self.result_data["jemalloc"]["purecap"].keys()]:
        if self.result_data[lib]["hybrid"][bm]["total-time"] == 0.0 \
           or  self.result_data[lib]["purecap"][bm]["total-time"] == 0.0 : 
          removed = self.result_data.pop(lib) 
          print(f"Removing incomplete data due to "
                f"{lib}[{bm}][hybrid][total-time] or "
                f"{lib}[{bm}][purecap][total-time] = 0.0")
          break
    #else:
    #  with open(self.out_file, "w") as fd:
    #    json.dump(self.result_data, fd , indent=2,sort_keys=True)

  def _normalise_results(self):
    new_time = {} 
    libs = [ _lib for _lib in self.result_data.keys() if _lib != "jemalloc" ] 

    for lib in libs: 
      new_time[lib] = {\
         "hybrid": { 
                     _bm: { f"normalised-{_evt}": 
                            self.result_data[lib]["hybrid"][_bm][_evt]/ self.result_data["jemalloc"]["hybrid"][_bm][_evt]
                            for _evt in self.events}
                     for _bm in self.result_data[lib]["hybrid"].keys()
                   }, 
         "purecap" : { 
                     _bm: { f"normalised-{_evt}": 
                            self.result_data[lib]["purecap"][_bm][_evt]/ self.result_data["jemalloc"]["purecap"][_bm][_evt]
                            for _evt in self.events}
                     for _bm in self.result_data[lib]["purecap"].keys()
                   } 
         }          

    raw_data_out = self.out_file.parent.resolve()/f"{self.out_file.stem}_alloctime.json"
    with open(raw_data_out, "w") as fd:
      json.dump(new_time, fd , indent=2,sort_keys=True)

    return new_time
                      

  def normalised_alloc_plot(self, conf_interval=99):
    for _evt in self.events: 
      self.gen_barchart(_evt, conf_interval)
      self.render(_evt)

  def gen_barchart(self, event, conf_interval):
    _gmean = lambda _arr : np.exp(np.log(_arr).mean()) if np.count_nonzero(_arr) == _arr.size else 0.0

    tick_lbl, tick_x, bar_x = self.gen_bunched_bar_loc( bw=0.5, sw=1.0, offset=0.5)

    _fig, _subplot = plt.subplots(nrows=1, ncols=1, sharex=False)
    _fig.tight_layout()

    geo_evt_hybrid, geo_evt_purecap = ([], [])
    for _alloc in tick_lbl:
      bm_events_hybrid = [ self.normal_time[_alloc]["hybrid"][_bm][f"normalised-{event}"] \
                              for _bm in self.normal_time[_alloc]["hybrid"].keys()]
      bm_events_purecap = [ self.normal_time[_alloc]["purecap"][_bm][f"normalised-{event}"] \
                              for _bm in self.normal_time[_alloc]["purecap"].keys()]

      geo_evt_hybrid += [ _gmean(np.array(bm_events_hybrid))] 
      geo_evt_purecap += [ _gmean(np.array(bm_events_purecap)) ]

    _subplot.bar( bar_x[0] , geo_evt_hybrid, 
                   label=event, color=m_arch_colors["hybrid"], width=0.5)
    _subplot.bar( bar_x[1] , geo_evt_purecap, 
                   label=event, color=m_arch_colors["purecap"], width=0.5)
    _subplot.grid(True)
    _subplot.set_xticks(tick_x)
    _subplot.set_xticklabels( tick_lbl , rotation=0.0, fontsize="medium")
    _subplot.set_ylabel("Normalised (vs jemalloc) allocated time taken", fontsize="large")
    _subplot.legend(loc=0,ncol=2, fontsize='large')
                        

  def gen_bunched_bar_loc(self, bw=0.5, sw=0.5, offset=0.5):
    bins = ["hybrid", "purecap"]
    tick_pos, bar_pos = ([], [ [] for _i in bins])
    num_bins = len(bins)
    tick_labels = [ _key for _key in self.result_data.keys() if _key != 'jemalloc']

    # Calculate bar and tick positions
    bin_start = offset
    for idx_i in range(len(tick_labels)):
      data_end = bin_start + ((num_bins)*bw)
      benchmark_end = bin_start + ((num_bins)*bw) + sw
      for _bin in range(num_bins):
        bar_pos[_bin].append(bin_start + (_bin * bw) + bw/2)
      tick_pos.append((data_end + bin_start)/2)
      bin_start = benchmark_end 

    return (tick_labels, tick_pos, bar_pos)


  def render(self, event, adjust=None):
    if adjust != None :
      _left, _right, _bottom, _top, _hspace = adjust
      plt.subplots_adjust(left=_left,right=_right,bottom=_bottom,top=_top,hspace=_hspace)
    
    _suffix = self.out_file.suffix.lstrip(".")
    assert _suffix.lstrip(".") in out_formats, f"invalid output file ({self.out_file})format {_suffix.lstrip('.')}. " \
                                                                  f"acceptable formats -> {out_formats}"
    
    plt.draw()
    plt.pause(1)
    input("<Press Enter to continue>")
    filename = self.out_file.parent.resolve()/f"{self.out_file.stem}_{event}.pdf"
    plt.savefig(filename, format="pdf")
    plt.close()

if __name__ == '__main__':
  parser = argparse.ArgumentParser(prog = sys.argv[0], 
                          description = f"Generate barcharts from json results file") 
  parser.add_argument('-i', '--infile',
                      required = True, 
                      help=f"input-data file name")
  parser.add_argument('-o', '--outfile',
                      default = 'output.pdf',
                       help=f"output-plot file name. suffix should end in {out_formats}")
  parser.add_argument('-t', '--graphtypes', nargs='*',
                             choices = ['individual', 'combined', 'alloc-times'],
                             default = ['individual'],
                             help=f"graph types to plot execute. These may be combined together to do both")
  parser.add_argument('-e', '--events', nargs='*',
                             choices = ['total-time', 'rss-kb', 'MEM_ACCESS', 'L2D_CACHE', 'L1D_CACHE', \
                                        'L1I_CACHE', 'INST_RETIRED', 'CPU_CYCLES', 'BUS_ACCESS', \
                                        'LL_CACHE_RD', 'LL_CACHE_MISS_RD', 'BUS_ACCESS_RD_CTAG', \
                                        'gc-cycles', 'gc-time', 'gc-load'],
                             default = ['total-time'],
                             help=f"graph types to plot execute. These may be combined together to do both")


  args = parser.parse_args() 
  _input, _output = (pathlib.Path(args.infile), pathlib.Path(args.outfile).resolve())
  assert _input.exists(), f"Input file {_input} does not exist"
  assert _input.is_file(), f"Input {_input} is not a file"

  if 'individual' in args.graphtypes:
    plot("histogram", _input, _output, (["gc-cycles", "gc-time"],["gc-load"]), True, conf_interval=98)
  if 'combined' in args.graphtypes:
    norm_graph = Combined_Graphs( "histogram", _input, _output)
    norm_graph.combined_normalised_plot((args.events, []), conf_interval=98)
  if 'alloc-times' in args.graphtypes:
    alloc_times = GeoMean_Allocators( "histogram", _input, _output, ["total-time"])
    alloc_times.normalised_alloc_plot(False)
