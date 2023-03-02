import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

## Generate stacked bar chart of dynamic instruction mix by instr type

RELATIVE_RESULTS = 1  # set to for absolute results in bar graph

df = pd.read_csv('counts.csv', sep=",", header=0)
del df[df. columns[-1]]
df.columns= df.columns.str.lower()
##df.index = components
print(df)


## fiddle data columns ...
df['data proc reg (user)'] += df['data proc imm (user)']
del df['data proc imm (user)']
df.rename(columns={'data proc reg (user)':'data proc (user)'}, inplace=True)

# find benchmarks
benchmarks = []
for exp in df['bm-config']:
    bm = exp.split('-')[0]
    if bm not in benchmarks:
        benchmarks.append(bm)

# find user metrics
user_metrics = []
for metric in df.columns:
    if 'user' in metric:
        user_metrics.append(metric)

# remove kernel metrics
kernel_metrics = []
for metric in df.columns:
    if 'kernel' in metric:
        kernel_metrics.append(metric)

for metric in kernel_metrics:
    del df[metric]


def find_color(metric):
    if metric.startswith('data proc'):
        return 'dimgray'
    if metric.startswith('scalar fp'):
        return 'salmon'
    if metric.startswith('branches'):
        return 'whitesmoke'
    if metric.startswith('loads and stores'):
        return 'sandybrown'
    if metric.startswith('morello arith'):
        return 'lightseagreen'
    if metric.startswith('morello ld/st'):
        return 'cadetblue'
    if metric.startswith('morello mis'):
        return 'skyblue'
    if metric.startswith('morello regs'):
        return 'dodgerblue'
    return 'black'

def find_hatch(metric):
    if metric.startswith('morello'):
        return '...'
    else:
        return ''

def tidy_up_name(metric):
    name = metric.split(' (')[0]
    if name == 'loads and stores':
        name = 'ld/st'
    return name
    
instr_colours = [ 'dimgray', 'silver', 'whitesmoke', 'salmon', 'sandybrown',
                  'dodgerblue', 'skyblue', 'cadetblue', 'lightseagreen', 'turquoise']



width = 0.25  # the width of the bars

hatchings = ([' ']*5) + (['/']*5)

if RELATIVE_RESULTS:
    ######### Do normalization of results
    hybrid_totals = {}  # key on benchmark, value is sum of user instructions
    for benchmark in benchmarks:
        instr_counts = df[df['bm-config'] == benchmark+'-hybrid']
        sum = 0
        for metric in user_metrics:
            sum += int(instr_counts[metric])
        hybrid_totals[benchmark] = sum
        
    

        # convert instr counts to floating-point
    for metric in user_metrics:
        df[metric] = df[metric].astype(float)
    
    for benchmark in benchmarks:
        hybrid_total = float(hybrid_totals[benchmark])

    def normalize(exp, metric_value):
        benchmark = exp.split('-')[0]
        hybrid_total = hybrid_totals[benchmark]
        return metric_value * 100/hybrid_total
    
    
    for metric in user_metrics:
        df[metric] = df.apply(lambda row : normalize(row['bm-config'], row[metric]), axis = 1)
    

#### Now plot results
fig, ax = plt.subplots(constrained_layout=True)
##fig, ax = plt.subplots()

purecap_results = df[df['bm-config'].str.endswith('purecap')]
x = np.arange(len(purecap_results))  # the label locations
###print(purecap_results)

prev = [0]*len(benchmarks) ## -- store previous value for stacking
                           ## is this one per metric, or one per bm?

for metric in user_metrics:
    # offset = width * multiplier  -- add offset for purecap/hybrid
    rects = ax.bar(x-(width/2), purecap_results[metric], width=width, bottom = prev, label=tidy_up_name(metric), edgecolor='black', color=find_color(metric), hatch=find_hatch(metric))
    prev += purecap_results[metric]
    ## ax.bar_label(rects, padding=3)


hybrid_results = df[df['bm-config'].str.endswith('hybrid')]
x = np.arange(len(hybrid_results))  # the label locations
###print(hybrid_results)

prev = [0]*len(benchmarks) ## -- store previous value for stacking
                           ## is this one per metric, or one per bm?

for metric in user_metrics:
    # offset = width * multiplier  -- add offset for purecap/hybrid
    rects = ax.bar(x+(width/2), hybrid_results[metric], width=width, bottom = prev, edgecolor='black', color=find_color(metric), hatch=find_hatch(metric))
    prev += hybrid_results[metric]
    ## ax.bar_label(rects, padding=3)
    

ax.set_xticks(x, benchmarks, rotation=90)
    
# automatic stacked bar chart 
##ax = df.plot(x='bm-config', kind='bar', stacked=True, ##color=instr_colours,
##             hatch='', edgecolor='black',
##        title='Morello benchmarks instruction mix')


# ax.bar(df.columns, df.loc[components[-1]], label=components[-1])
# baseline = df.loc[components[-1]]
# for i in range(len(components)-2, -1, -1):
#     ax.bar(df.columns, df.loc[components[i]], label=components[i],
#            bottom = baseline)
#     baseline += df.loc[components[i]]
    

if not RELATIVE_RESULTS:
    ax.set_ylabel('num instructions')
else:
    ax.set_ylabel('% instructions relative to hybrid total')
    
##ax.set_title('Per-benchmark instruction mix')

#box = ax.get_position()
#ax.set_position([box.x0, box.y0, box.width * 0.5, box.height])



handles, labels = ax.get_legend_handles_labels()
ax.legend(reversed(handles), reversed(labels), loc='upper right', bbox_to_anchor = (1.5, 0.6))

# handles, labels = plt.gca().get_legend_handles_labels()
# ##order = list(range(len(components)))
# order = list(range(len(components)-1, -1, -1))
# plt.legend([handles[idx] for idx in order],[labels[idx] for idx in order], loc='center left', bbox_to_anchor=(1, 0.5))

# ##ax.legend()

plt.tight_layout()

plt.savefig('stacked_bar_chart.pdf')
plt.show()
