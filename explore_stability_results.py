import json
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import pandas as pd

with open("results_chains_f52dc0e9-976b-40e6-9a5d-3f3238e35e51.json", "r") as f:
    chain_results = json.load(f)

with open(
    "results_assistants_dd136e73-73ad-4c03-bdcb-6946c66610b1.json",
    "r",
) as f:
    assitant_results = json.load(f)
# chain_results = json.load()

keys = list(chain_results.keys())
data = []
for key in keys:
    for distance_chain, distance_assistant in zip(
        chain_results[key]["distances"], assitant_results[key]["distances"]
    ):
        data.append({"distance": distance_chain, "type": "chain", "name": key})
        data.append({"distance": distance_assistant, "type": "assistant", "name": key})

df = pd.DataFrame.from_records(data, columns=["distance", "type", "name"])
print(df)


sns.boxplot(x=df["name"], y=df["distance"], hue=df["type"])

plt.show()


# data = []
# names = []
# for key in keys:
#     names.append(key)
#     data.append(chain_results[key]['distances'])

# fig = plt.figure(figsize =(10, 7))
# ax = fig.add_subplot(111)

# bp = ax.boxplot(data, patch_artist = True,
#                 notch ='True', vert = 0)

# colors = ['#0000FF', '#00FF00',
#           '#FFFF00', '#FF00FF']

# for patch, color in zip(bp['boxes'], colors):
#     patch.set_facecolor(color)

# # changing color and linewidth of
# # whiskers
# for whisker in bp['whiskers']:
#     whisker.set(color ='#8B008B',
#                 linewidth = 1.5,
#                 linestyle =":")

# # changing color and linewidth of
# # caps
# for cap in bp['caps']:
#     cap.set(color ='#8B008B',
#             linewidth = 2)

# # changing color and linewidth of
# # medians
# for median in bp['medians']:
#     median.set(color ='red',
#                linewidth = 3)

# # changing style of fliers
# for flier in bp['fliers']:
#     flier.set(marker ='D',
#               color ='#e7298a',
#               alpha = 0.5)

# # x-axis labels
# ax.set_yticklabels(names)

# # Adding title
# plt.title("Distribution of distances between chain calls")

# # Removing top axes and right axes
# # ticks
# ax.get_xaxis().tick_bottom()
# ax.get_yaxis().tick_left()

# # show plot
# plt.show()


# # import numpy as np; np.random.seed(1)
# # import matplotlib.pyplot as plt

# # A = np.random.rand(100,10)
# # B = np.random.rand(100,10)

# def draw_plot(data, offset,edge_color, fill_color):
#     pos = np.arange(data.shape[1])+offset
#     bp = ax.boxplot(data, positions= pos, widths=0.3, patch_artist=True, manage_xticks=False)
#     for element in ['boxes', 'whiskers', 'fliers', 'medians', 'caps']:
#         plt.setp(bp[element], color=edge_color)
#     for patch in bp['boxes']:
#         patch.set(facecolor=fill_color)

# fig, ax = plt.subplots()
# draw_plot(data_chains, -0.2, "tomato", "white")
# draw_plot(data_assistants, +0.2,"skyblue", "white")
# plt.title("Distribution of distance")
# plt.xticks(range(10))
# ax.set_xticklabels(names)
# # plt.savefig(__file__+'.png', bbox_inches='tight')
# plt.show()
# # plt.close()
