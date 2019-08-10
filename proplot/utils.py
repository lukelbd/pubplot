#!/usr/bin/env python3
"""
Simple tools used in various places across this package.
"""
import os
import re
import time
import glob
import numpy as np
import warnings
import functools
import matplotlib as mpl
import matplotlib.font_manager as mfonts
from numbers import Number, Integral
rcParams = mpl.rcParams
try:
    from icecream import ic
except ImportError:  # graceful fallback if IceCream isn't installed.
    ic = lambda *a: None if not a else (a[0] if len(a) == 1 else a) # noqa
__all__ = ['arange', 'edges', 'units']

#-----------------------------------------------------------------------------#
# Important private helper funcs
#-----------------------------------------------------------------------------#
_data_user_paths = {*()}
_data_allowed_paths = {'cmaps', 'cycles', 'fonts'}
def _check_data():
    """Checks the data folder and issues helpful warning message for new users.
    This is called inside every register function."""
    global _data_user_paths
    data_user = os.path.join(os.path.expanduser('~'), '.proplot')
    data_user_paths = {os.path.basename(path) for path in glob.glob(os.path.join(data_user, '*'))}
    if data_user_paths!=_data_user_paths and data_user_paths>_data_allowed_paths:
        _data_user_paths = data_user_paths
        warnings.warn(f'Found extra files {", ".join(data_user_paths - _data_allowed_paths)} in the ~/.proplot folder. Files must be placed in the .proplot/cmaps, .proplot/cycles, or .proplot/fonts subfolders.')

def _default(*args):
    """Returns the first non-``None`` value, used with keyword arg aliases and
    for setting default values."""
    for arg in args:
        if arg is not None:
            return arg
    return arg # last one

#-----------------------------------------------------------------------------#
# Decorators
#-----------------------------------------------------------------------------#
def _timer(func):
    """A decorator that prints the time a function takes to execute.
    See: https://stackoverflow.com/a/1594484/4970632"""
    @functools.wraps(func)
    def decorator(*args, **kwargs):
        t = time.clock()
        print(f'{func.__name__}()')
        res = func(*args, **kwargs)
        print(f'{func.__name__}() time: {time.clock()-t}s')
        return res
    return decorator

def _logger(func):
    """A decorator that logs the activity of the script (it actually just prints it,
    but it could be logging!). See: https://stackoverflow.com/a/1594484/4970632"""
    @functools.wraps(func)
    def decorator(*args, **kwargs):
        res = func(*args, **kwargs)
        print(f'{func.__name__} called with: {args} {kwargs}')
        return res
    return decorator

def _counter(func):
    """A decorator that counts and prints the cumulative time a function
    has benn running. See: https://stackoverflow.com/a/1594484/4970632"""
    @functools.wraps(func)
    def decorator(*args, **kwargs):
        t = time.clock()
        res = func(*args, **kwargs)
        decorator.time += (time.clock() - t)
        decorator.count += 1
        print(f'{func.__name__} cumulative time: {decorator.time}s ({decorator.count} calls)')
        return res
    decorator.time = 0
    decorator.count = 0 # initialize
    return decorator

#-----------------------------------------------------------------------------#
# Accessible for user
#-----------------------------------------------------------------------------#
def arange(min_, *args):
    """Identical to `numpy.arange`, but with inclusive endpoints. For
    example, ``plot.arange(2,4)`` returns ``np.array([2,3,4])``."""
    # Optional arguments just like np.arange
    if len(args)==0:
        max_ = min_
        min_ = 0
        step = 1
    elif len(args)==1:
        max_ = args[0]
        step = 1
    elif len(args)==2:
        max_ = args[0]
        step = args[1]
    else:
        raise ValueError('Function takes from one to three arguments.')
    # All input is integer
    if all(isinstance(val,Integral) for val in (min_,max_,step)):
        min_, max_, step = np.int64(min_), np.int64(max_), np.int64(step)
        max_ += 1
    # Input is float or mixed, cast to float64
    # Don't try to increment to next float, because round-off errors from
    # continually adding step to min mess this up. Just use max plus step/2.
    # max_ = np.nextafter(max_, np.finfo(np.dtype(np.float64)).max)
    else:
        min_, max_, step = np.float64(min_), np.float64(max_), np.float64(step)
        max_ += step/2
    return np.arange(min_, max_, step)

def edges(values, axis=-1):
    """Returns approximate edge values along the axis `axis`. This can be used
    e.g. when you have grid centers and need to calculate grid edges for a
    `~matplotlib.axes.Axes.pcolor` or `~matplotlib.axes.Axes.pcolormesh` plot."""
    # First permute
    values = np.array(values)
    values = np.swapaxes(values, axis, -1)
    # Next operate
    flip = False
    idxs = [[0] for _ in range(values.ndim-1)] # must be list because we use it twice
    if values[np.ix_(*idxs, [1])] < values[np.ix_(*idxs, [0])]:
        flip = True
        values = np.flip(values, axis=-1)
    values = np.concatenate((
        values[...,:1]  - (values[...,1]-values[...,0])/2,
        (values[...,1:] + values[...,:-1])/2,
        values[...,-1:] + (values[...,-1]-values[...,-2])/2,
        ), axis=-1)
    if flip:
        values = np.flip(values, axis=-1)
    # Permute back and return
    values = np.swapaxes(values, axis, -1)
    return values

#-----------------------------------------------------------------------------#
# Units
#-----------------------------------------------------------------------------#
def units(value, numeric='in'):
    """
    Flexible units -- this function is used internally all over ProPlot, so
    that you don't have to use "inches" or "points" for all sizing arguments.
    See `this link <http://iamvdo.me/en/blog/css-font-metrics-line-height-and-vertical-align#lets-talk-about-font-size-first>`_
    for info on the em square units.

    Parameters
    ----------
    value : float or str or list thereof
        A size "unit" or *list thereof*. If numeric, assumed unit is `numeric`.
        If string, we look for the format ``'123.456unit'``, where the
        number is the value and ``'unit'`` is one of the following.

        ======  ===================================================================
        Key     Description
        ======  ===================================================================
        ``m``   Meters
        ``cm``  Centimeters
        ``mm``  Millimeters
        ``ft``  Feet
        ``in``  Inches
        ``pt``  Points (1/72 inches)
        ``px``  Pixels on screen, uses dpi of ``rc['figure.dpi']``
        ``pp``  Pixels once printed, uses dpi of ``rc['savefig.dpi']``
        ``em``  Em-square for ``rc['font.size']``
        ``ex``  Ex-square for ``rc['font.size']``
        ``Em``  Em-square for ``rc['axes.titlesize']``
        ``Ex``  Ex-square for ``rc['axes.titlesize']``
        ======  ===================================================================

    numeric : str, optional
        The assumed unit for numeric arguments, and the output unit. Default
        is ``'in'``.
    """
    # Loop through arbitrary list, or return None if input was None (this
    # is the exception).
    if value is None:
        return value
    if not np.iterable(value) or isinstance(value, str):
        singleton = True
        values = (value,)
    else:
        singleton = False
        values = value

    # Font unit scales
    small = rcParams['font.size'] # must be absolute
    large = rcParams['axes.titlesize']
    if isinstance(large, str):
        scale = mfonts.font_scalings.get(large, 1) # error will be raised somewhere else if string name is invalid!
        large = small*scale

    # Dict of possible units
    unit_dict = {
        # Physical units
        'in': 1.0, # already in inches
        'm':  39.37,
        'ft': 12.0,
        'cm': 0.3937,
        'mm': 0.03937,
        'pt': 1/72.0,
        # Font units
        'em': small/72.0,
        'ex': 0.5*small/72.0, # more or less; see URL
        'Em': large/72.0, # for large text
        'Ex': 0.5*large/72.0,
        }
    # Display units
    # WARNING: In ipython shell these take the value 'figure'
    if not isinstance(rcParams['figure.dpi'], str):
        unit_dict['px'] = 1/rcParams['figure.dpi'] # on screen
    if not isinstance(rcParams['savefig.dpi'], str):
        unit_dict['pp'] = 1/rcParams['savefig.dpi'] # once 'printed', i.e. saved

    # Iterate
    try:
        scale = unit_dict[numeric]
    except KeyError:
        raise ValueError(f'Invalid numeric unit {numeric}. Valid units are {", ".join(unit_dict.keys())}.')
    result = []
    for value in values:
        if isinstance(value, Number):
            result.append(value)
            continue
        elif not isinstance(value, str):
            raise ValueError(f'Size spec must be string or number or list thereof, received {values}.')
        regex = re.match('^([0-9.]*)(.*)$', value)
        num, unit = regex.groups()
        try:
            result.append(float(num)*unit_dict[unit]/scale)
        except (KeyError, ValueError):
            raise ValueError(f'Invalid size spec {value}. Valid units are {", ".join(unit_dict.keys())}.')
    if singleton:
        result = result[0]
    return result

#-----------------------------------------------------------------------------#
# Outdated
#-----------------------------------------------------------------------------#
# Throw this one out, use kwarg interpolation from method.
# Why? Because matplotlib plot_directive sphinx extension will look for
# gallery images in the old documentation that do not exist for ProPlot.
# from inspect import cleandoc
# def _docstring_fix(child):
#     """
#     Decorator function for appending documentation from overridden method
#     onto the overriding method docstring.
#     Adapted from: https://stackoverflow.com/a/8101598/4970632
#     """
#     for name,chfunc in vars(child).items(): # returns __dict__ object
#         if not callable(chfunc): # better! see: https://stackoverflow.com/a/624939/4970632
#             continue
#         for parent in getattr(child, '__bases__', ()):
#             # Obtain documentation
#             parfunc = getattr(parent, name, None)
#             if not getattr(parfunc, '__doc__', None):
#                 continue
#             if not getattr(chfunc, '__doc__', None):
#                 chfunc.__doc__ = '' # in case it's None
#
#             # Ugly
#             # cmessage = f'Full name: {parfunc.__qualname__}()'
#             # pmessage = f'Parent method (documentation below): {chfunc.__qualname__}()'
#             # chfunc.__doc__ = f'\n{cmessage}\n{cleandoc(chfunc.__doc__)}\n{pmessage}\n{cleandoc(parfunc.__doc__)}'
#
#             # Simple
#             # chfunc.__doc__ = f'{cleandoc(chfunc.__doc__)}\n\n\n{cleandoc(parfunc.__doc__)}'
#
#             # Fails because numpydoc disallows custom subsections; see: https://developer.lsst.io/python/numpydoc.html#sections-are-restricted-to-the-numpydoc-section-set
#             # chfunc.__doc__ = f'ProPlot Override\n================\n{cleandoc(chfunc.__doc__)}\n\n\n' \
#             #                  f'Original Documentation\n======================\n{cleandoc(parfunc.__doc__)}'
#
#             # Differentiate with bold text
#             chfunc.__doc__ = f'**ProPlot Override**\n{cleandoc(chfunc.__doc__)}\n\n\n' \
#                              f'**Original Documentation**\n{cleandoc(parfunc.__doc__)}'
#             break # only do this for the first parent class
#     return child

