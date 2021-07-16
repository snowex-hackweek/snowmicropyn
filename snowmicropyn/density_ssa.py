"""Calculation of density and ssa.

This module implements the methods to derive density and specific surface area
(SSA) from SnowMicroPen's signal as described in publication
`Density, specific surface area, and correlation length of snow measured by
high‐resolution penetrometry <https://doi.org/10.1002/2014JF003266>`_ by Martin
Proksch, Henning Löwe and Martin Schneebeli, publicised in `Journal of
Geophysical Research: Earth Surface
<https://agupubs.onlinelibrary.wiley.com/journal/21699011>`_, Volume 120,
Issue 2, February 2015.

"""

import numpy as np
import pandas as pd
import warnings

import snowmicropyn.loewe2012
import snowmicropyn.windowing
import snowmicropyn.profile as profile

DENSITY_ICE = 917.


def calc_step(median_force, element_size, coeff_model):
    """Calculation of density and ssa from median of force and element size.

    This is the actual math described in the publication.

    :param median_force: Median of force.
    :param element_size: Element size.
    :return: Tuple containing density and ssa value.
    """
    l = element_size
    fm = median_force

    # Specify log_l = False to use Proksch form of SSA regression equation or log_l = True to use Calonne version

    if coeff_model is None:
        # Use Proksch et al. (2015) coefficients if not specified (eqn 9 and 11)
        coeffs = {'density':[420.47, 102.47, -121.15, -169.96], 'ssa':[0.131, 0.355, 0.0291], 'equation':'l_ex'}
    elif coeff_model == 'P2015':
        # Proksch et al. (2015)
        coeffs = {'density':[420.47, 102.47, -121.15, -169.96], 'ssa':[0.131, 0.355, 0.0291], 'equation':'l_ex'}
    elif coeff_model == 'C2020':
        # Calonne et al. 2020 https://doi.org/10.5194/tc-14-1829-2020
        coeffs = {'density': [295.8, 65.1, -43.2, 47.1], 'ssa':[0.57, -18.56, -3.66], 'equation':'ssa'}
    elif coeff_model == 'K2020a':
        # King et al. 2020 https://doi.org/10.5194/tc-14-4323-2020 Table 2
        coeffs = {'density':[315.61, 46.94, -43.94, -88.15], 'ssa':[np.nan, np.nan, np.nan], 'equation':'ssa'}
    elif coeff_model == 'K2020b':
        # King et al. 2020 https://doi.org/10.5194/tc-14-4323-2020 Table 2
        coeffs = {'density': [312.54, 50.27, -50.26, -85.35], 'ssa':[np.nan, np.nan, np.nan], 'equation':'ssa'}
    else:
        coeffs = coeff_model

    density = coeffs['density'][0] + coeffs['density'][1] * np.log(fm) + coeffs['density'][2] * np.log(fm) * l + coeffs['density'][3] * l

    if coeffs['equation'] == 'ssa':
        # Use Calonne version
        ssa = coeffs['ssa'][0] + coeffs['ssa'][1] * np.log(l) + coeffs['ssa'][2] * np.log(fm)
    elif coeffs['equation'] == 'l_ex':
        # Use Proksch version
        lc = coeffs['ssa'][0] + coeffs['ssa'][1] * l + coeffs['ssa'][2] * np.log(fm)
        # Equation 12 in publication
        ssa = 4 * (1 - (density / DENSITY_ICE)) / lc
    else:
        warnings.warn('ssa equation form is not recognized. Expecting "l_ex" or "ssa"')
        ssa = np.nan

    return density, ssa


def calc(samples, coeff_model=None, window=snowmicropyn.windowing.DEFAULT_WINDOW, overlap=snowmicropyn.windowing.DEFAULT_WINDOW_OVERLAP):
    """Calculate ssa and density from a pandas dataframe containing the samples
    of a SnowMicroPen recording.

    :param samples: A pandas dataframe containing the columns 'distance' and 'force' or list of profiles containing these (will find median)
    :param coeffs [Optional]: dict of coefficients for calculating density and ssa. Defaults to Proksch et al. (2015)
    :param window: Size of window in millimeters.
    :param overlap: Overlap factor in percent.
    :return: A pandas dataframe with the columns 'distance', 'density' and 'ssa'.
    """

    if coeff_model == 'C2020':
        # Calonne et al. 2020 https://doi.org/10.5194/tc-14-1829-2020
        window = 1
        overlap = 50
    elif coeff_model == 'K2020a':
        # King et al. 2020 https://doi.org/10.5194/tc-14-4323-2020 Table 2
        window = 5
        overlap = 50
    elif coeff_model == 'K2020b':
        # King et al. 2020 https://doi.org/10.5194/tc-14-4323-2020 Table 2
        window = 5
        overlap = 50
    else:
        # Use defaults for Proksch 2015
        pass

    if isinstance(samples, list):
        sn = median_profile(samples, window, overlap)
    else:
        # Apply filtering to remove -ve force and linearly interpolate
        samples.loc[samples['force'] < 0, 'force'] = np.nan
        samples.force.interpolate(method='linear', inplace=True)
        sn = snowmicropyn.loewe2012.calc(samples, window, overlap)

    result = []
    for index, row in sn.iterrows():
        density, ssa = calc_step(row.force_median, row.L2012_L, coeff_model)
        result.append((row.distance, density, ssa))
    return pd.DataFrame(result, columns=['distance', 'density', 'ssa'])


def median_profile(list_of_filenames, window, overlap):
    
    '''
    Function to calculate the median force of several SMP profiles. 
    Avoids negative SSA when single profile used (but not completely).

    NB no filtering applied here - finding median should eliminate -ve forces

    Crops to length of shortest profile from the surface. Used detected surface and ground.
    Then calculates median force and structural element length for each profile from loewe2012 method
    Then finds medians of the median force and structural element length for all profiles

    :param list_of_filenames: List of SMP filenames used to generate median profile
        
    '''    
    
    # Find shortest profile
    shortest_length = min([(profile.Profile(p).detect_ground() - profile.Profile(p).detect_surface()) for p in list_of_filenames])
    # Get depth resolution of samples
    depth_step = profile.Profile(list_of_filenames[0]).samples.distance.diff().iloc[-1]
    # Get final resolution from windowing method
    final_resolution = window - (window * overlap) / 100
    # NB detect_ground is at measured height, detect_surface is between measured heights
    # This still ignores first half layer i.e. surface is put at first measurement within snow
    nlayers = int(shortest_length / depth_step)
    final_nlayers = int(shortest_length / final_resolution)
    # Create pandas dataframe with depths - will add force for each profile later
    df = pd.DataFrame(np.arange(final_nlayers) * final_resolution, columns=['distance'])
    
    # Add cropped profile calculated median force and structural element length to dataframe
    for p in list_of_filenames:
        # Crop to surface NB original distance retained i.e. doesn't start at zero but think this is ok
        cropped_samples = profile.Profile(p).samples[profile.Profile(p).samples.distance > profile.Profile(p).detect_surface()][:nlayers]
        # force = profile.Profile(p).samples[profile.Profile(p).samples.distance > profile.Profile(p).detect_surface()]['force'].to_numpy(copy=True)[:nlayers]
        # Try to run loewe2012 calc
        profile_fandL = snowmicropyn.loewe2012.calc(cropped_samples, window, overlap)
        # Add to dataframe: column name is profile name followed by parameter of interest
        df[p+'_F'] = profile_fandL.force_median.values
        df[p+'_L'] = profile_fandL.L2012_L.values

        
    # Find median of forces
    df['force_median'] = df.loc[:,df.columns.str.endswith('pnt_F')].median(axis=1).to_numpy(copy=True)
    # Median of structural element length
    df['L2012_L'] = df.loc[:,df.columns.str.endswith('pnt_L')].median(axis=1).to_numpy(copy=True)
    # Add to df - keep all in local df for error checking
    #df['force'] = median_force
    
    return df #df[['distance', 'force']]