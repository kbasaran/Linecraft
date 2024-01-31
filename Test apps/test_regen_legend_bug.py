#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan 31 10:16:55 2024

@author: kerem
"""

import matplotlib.pyplot as plt
import numpy as np
import time

def make_randomized_curve():
    x = 2**np.arange(5, 10)
    y = 15 + 10 * np.random.random(len(x))
    return x, y

curves = []
names = []
for i in range(20):
    curve = make_randomized_curve()
    label = f"Curve {i:02d}"
    if i % 2 == 0 or i > 16:
        label = "_" + label
    curves.append(curve)
    names.append(label)


fig, ax = plt.subplots()
line2Ds = []
for curve, name in zip(curves, names):
    line, = ax.semilogx(*curve, label=name)
    line2Ds.append(line)
ax.set_ylim([10, 30])

legend = ax.legend(line2Ds[3:8], names[3:8])
ax.draw_artist(legend)
# plt.draw()


# time.sleep(1)
# ax.semilogx([40, 80, 160], [10, 30, 10], label="Test add")
# ax.legend()
# plt.draw()
