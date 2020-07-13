import argparse
import os
from collections import OrderedDict

import uproot

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np

from utils import make_dirs

from _plot_fractions import plot_fractions
from _plot_cov import plot_cov

import mplhep as hep
plt.style.use([hep.cms.style.ROOT, {'font.size': 24}])
plt.switch_backend('agg')

def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

parser = argparse.ArgumentParser()
parser.add_argument("-d",
                    "--dir",
                    default='',
                    help="Model/Fit dir")
parser.add_argument("-i",
                    "--input-file",
                    default='shapes.root',
                    help="Input shapes file")
parser.add_argument("--fit",
                    default=None,
                    choices={"prefit", "postfit"},
                    dest='fit',
                    help="Shapes to plot")
parser.add_argument("--3reg",
                    action='store_true',
                    dest='three_regions',
                    help="By default plots pass/fail region. Set to plot pqq/pcc/pbb")
parser.add_argument("--unmask",
                    action='store_false',
                    dest='mask',
                    help="Mask Higgs bins")
parser.add_argument("-o", "--output-folder",
                    default='plots',
                    dest='output_folder',
                    help="Folder to store plots - will be created if it doesn't exist.")
parser.add_argument("--year",
                    default=2017,
                    help="year label")

parser.add_argument("--scaleH",
                    type=str2bool,
                    default='True',
                    choices={True, False},
                    help="Scale Higgs signal in plots by 100")


pseudo = parser.add_mutually_exclusive_group(required=True)
pseudo.add_argument('--data', action='store_false', dest='pseudo')
pseudo.add_argument('--MC',   action='store_true', dest='pseudo')
pseudo.add_argument('--toys', action='store_true', dest='toys')

args = parser.parse_args()
if args.output_folder.split("/")[0] != args.dir:
    args.output_folder = os.path.join(args.dir, args.output_folder)
make_dirs(args.output_folder)

cdict = {
    'hqq': 'blue',
    'hbb': 'blue',
    'hcc': 'darkred',
    'wqq': 'lightgreen',
    'wcq': 'green',
    'qcd': 'gray',
    'tqq': 'plum',
    'zbb': 'dodgerblue',
    'zcc': 'red',
    'zqq': 'turquoise',
}

sdict = {
    'hqq': '-',
    'hbb': '-',
    'hcc': '-',
    'wqq': '-',
    'wcq': '-',
    'qcd': '-',
    'tqq': '-',
    'zbb': '-',
    'zcc': '-',
    'zqq': '-',
}

# Sequence of tuples because python2 is stupid
label_dict = OrderedDict([
    ('Data', 'Data'),
    ('MC', 'MC'),
    ('Toys', 'PostFit\nToys'),
    ('zbb', "$\mathrm{Z(b\\bar{b})}$"),
    ('zcc', "$\mathrm{Z(c\\bar{c})}$"),
    ('zqq', "$\mathrm{Z(q\\bar{q})}$"),
    ('wcq', "$\mathrm{W(c\\bar{q})}$"),
    ('wqq', "$\mathrm{W(q\\bar{q})}$"),
    ('hbb', "$\mathrm{H(b\\bar{b})}$"),
    ('hqq', "$\mathrm{H(b\\bar{b})}$"),
    ('hcc', "$\mathrm{H(c\\bar{c})}$"),
    ('qcd', "QCD"),
    ('tqq', "$\mathrm{t\\bar{t}}$"),
])


def full_plot(cats, pseudo=True, fittype="", mask=False,
              toys=False, 
              sqrtnerr=False):

    # Determine:
    if "pass" in str(cats[0].name) or "fail" in str(cats[0].name):
        regs = "pf"
    elif "pqq" in str(cats[0].name) or "pcc" in str(cats[0].name) or "pbb" in str(
            cats[0].name):
        regs = "3reg"
    else:
        print("Unknown regions")
        return

    # For masking 0 bins (don't want to show them)
    class Ugh():
        def __init__(self):
            self.plot_bins = None
    ugh = Ugh()

    def tgasym_to_err(tgasym):
        # https://github.com/cms-analysis/HiggsAnalysis-CombinedLimit/wiki/nonstandard
        # Rescale density by binwidth for actual value
        _binwidth = tgasym._fEXlow + tgasym._fEXhigh
        _x = tgasym._fX
        _y = tgasym._fY * _binwidth
        _xerrlo, _xerrhi = tgasym._fEXlow, tgasym._fEXhigh
        _yerrlo, _yerrhi = tgasym._fEYlow * _binwidth, tgasym._fEYhigh * _binwidth
        return _x, _y, _yerrlo, _yerrhi, _xerrlo, _xerrhi

    def plot_data(x, y, yerr, xerr, ax=None, pseudo=pseudo, ugh=None):
        if ugh is None:
            ugh = Ugh()
        data_err_opts = {
            'linestyle': 'none',
            'marker': '.',
            'markersize': 12.,
            'color': 'k',
            'elinewidth': 2,
        }
        if np.sum([y != 0][0]) > 0:
            if ugh.plot_bins is None:
                ugh.plot_bins = [y != 0][0]
            else:
                ugh.plot_bins = (ugh.plot_bins & [y != 0][0])

        x = np.array(x)[ugh.plot_bins]
        y = np.array(y)[ugh.plot_bins]

        yerr = [
            np.array(yerr[0])[ugh.plot_bins],
            np.array(yerr[1])[ugh.plot_bins]
        ]
        xerr = [
            np.array(xerr)[0][ugh.plot_bins],
            np.array(xerr)[1][ugh.plot_bins]
        ]

        if mask and not pseudo:
            _y = y
            _y[10:14] = np.nan
        else:
            _y = y

        _d_label = "MC" if pseudo else "Data"
        if toys: _d_label = "Toys"
        ax.errorbar(x,
                    y,
                    yerr,
                    xerr,
                    fmt='+',
                    label=_d_label,
                    **data_err_opts)

    def th1_to_step(th1):
        _h, _bins = th1.numpy()
        return _bins, np.r_[_h, _h[-1]]

    def th1_to_err(th1):
        _h, _bins = th1.numpy()
        _x = _bins[:-1] + np.diff(_bins)/2
        _xerr = [abs(_bins[:-1] - _x), _bins[1:] - _x]
        _var = th1.variances

        return _x, _h, _var, [_xerr[0], _xerr[1]]

    def plot_step(bins, h, ax=None, label=None, nozeros=True, **kwargs):
        if mask and not pseudo:
            _h = h
            #_h[10:14] = np.nan
        else:
            _h = h
        ax.step(bins, _h, where='post', label=label, c=cdict[label], **kwargs)

    def plot_filled(bins, h, h0=0, ax=None, label=None, nozeros=True, **kwargs):
        if h0 == 0:
            h0 = np.zeros_like(h)
        ax.fill_between(bins, h, h0, 
                        step='post', label=label, color=cdict[label], **kwargs)

    # Sample proofing
    by_cat_samples = []
    for _cat in cats:
        cat_samples = [
            k.decode(encoding="utf-8").split(';')[0] for k in _cat.keys()
            if b'total' not in k
        ]
        by_cat_samples.append(cat_samples)

    from collections import Counter
    count = Counter(sum(by_cat_samples, []))
    k, v = list(count.keys()), list(count.values())
    for _sample in np.array(k)[np.array(v) != max(v)]:
        print("Sample {} is partially or entirely missing and won't be plotted".format(
            _sample))

    avail_samples = list(np.array(k)[np.array(v) == max(v)])

    # Plotting
    fig, (ax, rax) = plt.subplots(2, 1,
                                  gridspec_kw={'height_ratios': (3, 1)},
                                  sharex=True)
    plt.subplots_adjust(hspace=0)

    #  Main
    # print(cats[0])
    res = np.array(list(map(th1_to_err, [cat['data_obs'] for cat in cats])))
    _x, _h = res[:, 0][0], np.sum(res[:, 1], axis=0)
    _xerr = res[:, -1][0]
    if sqrtnerr:
        _yerr = np.sqrt(_h)
    else:
        _yerr = np.sqrt(np.sum(res[:, 2], axis=0))
    plot_data(_x, _h, yerr=[_yerr, _yerr], xerr=_xerr, ax=ax, ugh=ugh)

    # Stack qcd/ttbar
    tot_h, bins = None, None
    for mc, zo in zip(['qcd', 'tqq'], [1, 0]):
        if mc not in avail_samples:
            continue
        res = np.array(list(map(th1_to_step, [cat[mc] for cat in cats])))
        bins, h = res[:, 0][0], np.sum(res[:, 1], axis=0)
        if tot_h is None:
            plot_step(bins, h, ax=ax, label=mc, zorder=zo)
            tot_h = h
        else:
            plot_step(bins, h + tot_h, label=mc, ax=ax, zorder=zo)
            tot_h += h

    # Stack plots
    tot_h, bins = None, None
    stack_samples = ['zbb', 'zcc', 'zqq', 'wcq', 'wqq']
    if not args.scaleH:
        stack_samples = ['hcc', 'hbb'] + stack_samples
    for mc in stack_samples:
        if mc not in avail_samples:
            continue
        res = np.array(list(map(th1_to_step, [cat[mc] for cat in cats])))
        bins, h = res[:, 0][0], np.sum(res[:, 1], axis=0)
        if tot_h is None:
            if mc == 'hcc':
                plot_filled(bins, h, h0=0, ax=ax, label=mc)
            else:
                plot_step(bins, h, ax=ax, label=mc)
            tot_h = h

        else:
            if mc == 'hcc':
                plot_filled(bins, h + tot_h, h0=tot_h, ax=ax, label=mc)
            else:
                plot_step(bins, h + tot_h, label=mc, ax=ax)
            tot_h += h

    # Separate scaled signal
    if args.scaleH:
        for mc in ['hcc', 'hbb']:
            if mc not in avail_samples:
                continue
            res = np.array(list(map(th1_to_step, [cat[mc] for cat in cats])))
            bins, h = res[:, 0][0], np.sum(res[:, 1], axis=0)
            plot_step(bins, h * 500, ax=ax, label=mc,
                      linestyle='--')


    #######
    # Ratio plot
    rax.axhline(0, c='gray', ls='--')

    # Caculate diff
    res = np.array(list(map(th1_to_err, [cat['data_obs'] for cat in cats])))
    _x, _y = res[:, 0][0], np.sum(res[:, 1], axis=0)
    _xerr = res[:, -1][0]
    if sqrtnerr:
        _yerr = np.sqrt(_h)
    else:
        _yerr = np.sqrt(np.sum(res[:, 2], axis=0))
    # _yerr += 0.0000000001  # pad zeros

    y = np.copy(_y)
    #for mc in ['qcd', 'tqq', 'wcq', 'wqq', 'zbb', 'zqq', 'hbb']:
    for mc in ['qcd', 'tqq']:
        if mc not in avail_samples:
            continue
        res = np.array(list(map(th1_to_step, [cat[mc] for cat in cats])))
        bins, h = res[:, 0][0], np.sum(res[:, 1], axis=0)
        y -= h[:-1]

    y /= _yerr
    _scale_for_mc = np.r_[_yerr,  _yerr[-1]]

    def prop_err(A, B, C, a, b, c):
        # Error propagation for (Data - Bkg)/Sigma_{Data} plot
        e = C**2 * (a**2 + b**2) + c**2 * (A - B)**2
        e /= (C**4 + 0.0000000001)  # pad zeros
        e = np.sqrt(e)
        return e

    # Error propagation, not sensitive to args[-1]
    err = prop_err(_y, _y-y, np.sqrt(_y), np.sqrt(_y), np.sqrt(_y-y), 1)

    plot_data(_x, y, yerr=[err, err], xerr=_xerr, ax=rax, ugh=ugh)

    # Stack plots
    tot_h, bins = None, None
    stack_samples = ['hbb', 'zbb', 'zcc', 'zqq', 'wcq', 'wqq']
    #stack_samples = ['zcc']
    if not args.scaleH:
        stack_samples = ['hcc', 'hbb'] + stack_samples
    for mc in stack_samples:
        if mc not in avail_samples:
            continue
        res = np.array(list(map(th1_to_step, [cat[mc] for cat in cats])))
        bins, h = res[:, 0][0], np.sum(res[:, 1], axis=0)
        if tot_h is None:
            if mc == 'hcc':
                plot_filled(bins, h / _scale_for_mc, ax=rax, label=mc)
            else:
                plot_step(bins, h / _scale_for_mc, ax=rax, label=mc)
            tot_h = h
        else:
            if mc == 'hcc':
                print("BINXO")
                plot_filled(bins, (h + tot_h)/_scale_for_mc, tot_h/_scale_for_mc, ax=rax, label=mc)
            else:
                plot_step(bins, (h + tot_h)/_scale_for_mc, label=mc, ax=rax)
            tot_h += h

    # Separate scaled signal
    if args.scaleH:
        for mc in ['hcc']:
            if mc not in avail_samples:
                continue
            res = np.array(list(map(th1_to_step, [cat[mc] for cat in cats])))
            bins, h = res[:, 0][0], np.sum(res[:, 1], axis=0)
            plot_step(bins, 500 * h / _scale_for_mc, ax=rax, label=mc,
                      linestyle='--')


    ############
    # Style
    lumi = {
        "jet": {
            "2016": 35.5,
            "2017": 41.5,
            "2018": 59.2,
        },
        "mu": {
            "2016": 35.2,
            "2017": 41.1,
            "2018": 59.0,
        }
    }
    if b'muon' in cats[0].name:
        lumi_t = "mu"
    else:
        lumi_t = "jet"
    ax = hep.cms.cmslabel(ax=ax, data=((not pseudo) | toys), year=args.year, 
                          lumi=lumi[lumi_t][str(args.year)],
                          fontsize=22)
    ax.legend(ncol=2)

    ax.set_ylabel('Events / 7GeV', ha='right', y=1)
    rax.set_xlabel('jet $\mathrm{m_{SD}}$ [GeV]', ha='right', x=1)
    rax.set_ylabel(
        #r'$\mathrm{\frac{Data-(MultiJet+t\bar{t})}{\sigma_{Data}}}$')
        r'$\mathrm{\frac{Data-Bkg}{\sigma_{Data}}}$')

    ax.set_xlim(40, 200)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.4)
    # ax.ticklabel_format(axis='y', style='sci', scilimits=(0,3), useOffset=False)
    # ax.yaxis.set_major_formatter(mtick.FormatStrFormatter('%.e'))
    f = mtick.ScalarFormatter(useOffset=False, useMathText=True)
    # g = lambda x, pos: "${}$".format(f._formatSciNotation('%1.10e' % x))

    def g(x, pos):
        return "${}$".format(f._formatSciNotation('%1.10e' % x))
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(g))
    rax.set_ylim(rax.get_ylim()[0] * 1.3, rax.get_ylim()[1] * 1.3)

    ipt = int(str(cats[0].name
                  ).split('ptbin')[1][0]) if b'ptbin' in cats[0].name else 0
    if len(cats) == 1:
        pt_range = str(pbins[ipt]) + "$< \mathrm{p_T} <$" + str(
            pbins[ipt + 1]) + " GeV"
    else:
        pt_range = str(pbins[0]) + "$< \mathrm{p_T} <$" + str(
            pbins[-1]) + " GeV"
    if b'muon' in cats[0].name:
        pt_range = str(pbins[0]) + "$< \mathrm{p_T} <$" + str(
            pbins[-1]) + " GeV"

    lab_mu = ", MuonCR" if b'muon' in cats[0].name else ""
    if regs == "pf":
        lab_reg = "Passing" if "pass" in str(cats[0].name) else "Failing"
    else:
        if "pqq" in str(cats[0].name):
            lab_reg = "Light"
        elif "pcc" in str(cats[0].name):
            lab_reg = "Charm"
        elif "pbb" in str(cats[0].name):
            lab_reg = "Bottom"

    annot = pt_range + '\nDeepDoubleX{}'.format(lab_mu) + '\n{} Region'.format(lab_reg)

    ax.annotate(annot,
                linespacing=1.7,
                xy=(0.04, 0.94),
                xycoords='axes fraction',
                ha='left',
                va='top',
                ma='center',
                fontsize='small',
                bbox={
                    'facecolor': 'white',
                    'edgecolor': 'white',
                    'alpha': 0,
                    'pad': 13
                },
                annotation_clip=False)

    # Leg sort
    if args.scaleH:
        label_dict['hcc'] = "$\mathrm{H(c\\bar{c})}$ x 500"
        label_dict['hqq'] = "$\mathrm{H(b\\bar{b})}$ x 500"
        label_dict['hbb'] = "$\mathrm{H(b\\bar{b})}$ x 500"

    sorted_handles_labels = hep.plot.sort_legend(ax, label_dict)
    # Insert dummy to uneven legend to align right
    if len(sorted_handles_labels[0]) % 2 != 0:
        _insert_ix = len(sorted_handles_labels[0])/2
        sorted_handles_labels[0].insert(
            _insert_ix, plt.Line2D([], [], linestyle='none', marker=None))
        sorted_handles_labels[1].insert(_insert_ix, '')
    leg = ax.legend(*sorted_handles_labels, ncol=2, columnspacing=0.8)
    leg.set_title(title=fittype.capitalize(), prop={'size': "smaller"})

    if b'muon' in cats[0].name:
        _iptname = "MuonCR"
    else:
        _iptname = str(str(ipt) if len(cats) == 1 else "")
    # name = str("pass" if "pass" in str(cats[0].name) else "fail"
    #            ) + _iptname
    name = str(lab_reg) + _iptname

    fig.savefig('{}/{}.png'.format(args.output_folder, fittype + "_" + name),
                bbox_inches="tight")


if args.fit is None:
    shape_types = ['prefit', 'postfit']
else:
    shape_types = [args.fit]
if args.three_regions:
    regions = ['pqq', 'pcc', 'pbb']
else:
    regions = ['pass', 'fail']

f = uproot.open(os.path.join(args.dir, args.input_file))
for shape_type in shape_types:
    pbins = [450, 500, 550, 600, 675, 800, 1200]
    for region in regions:
        print("Plotting {} region".format(region), shape_type)
        mask = (args.mask & (region == "pass")) | (args.mask & (region == "pcc"))  | (args.mask & (region == "pbb"))
        for i in range(0, 6):
            continue
            cat_name = 'ptbin{}{}_{};1'.format(i, region, shape_type)
            try:
                cat = f[cat_name]
            except Exception:
                raise ValueError("Namespace {} is not available, only following"
                                "namespaces were found in the file: {}".format(
                                    args.fit, f.keys()))

            fig = full_plot([cat], pseudo=args.pseudo, fittype=shape_type, mask=mask, toys=args.toys)
        full_plot([f['ptbin{}{}_{};1'.format(i, region, shape_type)] for i in range(0, 6)],
                   pseudo=args.pseudo, fittype=shape_type, mask=mask, toys=args.toys)
        # MuonCR if included
        try:
            cat = f['muonCR{}_{};1'.format(region, shape_type)]
            full_plot([cat], args.pseudo, fittype=shape_type, toys=args.toys)
            print("Plotted muCR", region, shape_type)
        except Exception:
            print("Muon region not found")
            pass

##### Input shape plotter
# Take sqrt N err for data
# Mock QCD while unavailable as template in rhalpha 
import os
from input_shapes import input_dict_maker
try:
    mockd = input_dict_maker(os.getcwd()+".pkl")

    input_pseudo = True
    if args.toys or not args.pseudo:
        input_pseudo = False
    for shape_type in ["inputs"]:
        pbins = [450, 500, 550, 600, 675, 800, 1200]
        for region in regions:
            print("Plotting inputs", region)
            _mask = not input_pseudo
            mask = (_mask & (region == "pass")) | (_mask & (region == "pcc"))  | (_mask & (region == "pbb"))
            full_plot([mockd['ptbin{}{}_{}'.format(i, region, shape_type)] for i in range(0, 6)],
                    pseudo=input_pseudo, fittype=shape_type, mask=mask, sqrtnerr=True, toys=False)

            # Per bin plots
            for i in range(0, 6):
                continue
                full_plot([mockd['ptbin{}{}_{}'.format(i, region, shape_type)]],
                    pseudo=input_pseudo, fittype=shape_type, mask=mask, sqrtnerr=True, toys=False)

            # MuonCR if included
            try:
                cat = mockd['muonCR{}_{}'.format(region, shape_type)]
                full_plot([cat], fittype=shape_type,
                        pseudo=input_pseudo, mask=False, sqrtnerr=True, toys=False)
                print("Plotted input, muCR", region, shape_type)
            except Exception:
                print("Muon region not found")
                pass
except:
    print("Input pkl file not found")

if args.three_regions:
    plot_fractions(os.path.join(args.dir, 'fitDiagnostics.root'),
                   os.path.join(args.dir, 'model_combined.root'),
                   out='{}/{}.png'.format(args.output_folder, 'fractions'),
                   data=((not args.pseudo) | args.toys), year=args.year,
    )

plot_cov(os.path.join(args.dir, 'fitDiagnostics.root'),
         out='{}/{}.png'.format(args.output_folder, 'covariances'),
         data=((not args.pseudo) | args.toys), year=args.year,
         )
