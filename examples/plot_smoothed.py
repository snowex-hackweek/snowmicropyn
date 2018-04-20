# Plotting the signal of a SMP profile using the library matploblib. An
# interactive plot is shown, you can pan, zoom, export by using the toolbar
# buttons.

import matplotlib as mpl
mpl.use('Qt4Agg')

from matplotlib import pyplot as plt

from scipy import signal
from snowmicropyn import Profile

p = Profile.load('./some_directory/S31M0067.pnt')

x, y = p.samples.distance, p.samples.force
y_smoothed = signal.savgol_filter(y, 242*5+1, 2)

plt.plot(x, y)
plt.plot(x, y_smoothed, 'r')

plt.title(p.name)
plt.ylabel('Force [N]')
plt.xlabel('Depth [mm]')

plt.show()
