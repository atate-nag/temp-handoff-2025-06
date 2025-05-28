# utils/capability_plot.py
import os, matplotlib.pyplot as plt

def generate_capability_plot(vrio_table: list[dict], company: str) -> str:
    x, y, labels = [], [], []
    for row in vrio_table:
        # crude mapping (value = V, sustainability = R + I)
        x.append(row["R"] + row["I"])
        y.append(row["V"] + (1 if row["O"] else 0))
        labels.append(row["name"][:20])
    fig, ax = plt.subplots(figsize=(6,6))
    sc = ax.scatter(x, y, s=80, c="dodgerblue", edgecolors="black")
    for lbl, ix, iy in zip(labels, x, y):
        ax.text(ix+0.1, iy, lbl, fontsize=8)
    ax.set_xlim(0,4); ax.set_ylim(0,4)
    ax.set_xlabel("Rarity + Inimitability"); ax.set_ylabel("Value + Organization")
    ax.set_title("VRIO Capability Map")
    img_path = os.path.join("./Strategic Reports/", f"{company}_capabilities.png")
    fig.tight_layout(); fig.savefig(img_path, dpi=300); plt.close(fig)
    return img_path
