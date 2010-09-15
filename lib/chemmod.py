# TAMkin is a post-processing toolkit for thermochemistry and kinetics analysis.
# Copyright (C) 2008-2010 Toon Verstraelen <Toon.Verstraelen@UGent.be>,
# Matthias Vandichel <Matthias.Vandichel@UGent.be> and
# An Ghysels <An.Ghysels@UGent.be>, Center for Molecular Modeling (CMM), Ghent
# University, Ghent, Belgium; all rights reserved unless otherwise stated.
#
# This file is part of TAMkin.
#
# TAMkin is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# In addition to the regulations of the GNU General Public License,
# publications and communications based in parts on this program or on
# parts of this program are required to cite the following five articles:
#
# "Vibrational Modes in partially optimized molecular systems.", An Ghysels,
# Dimitri Van Neck, Veronique Van Speybroeck, Toon Verstraelen and Michel
# Waroquier, Journal of Chemical Physics, Vol. 126 (22): Art. No. 224102, 2007
# DOI:10.1063/1.2737444
#
# "Cartesian formulation of the Mobile Block Hesian Approach to vibrational
# analysis in partially optimized systems", An Ghysels, Dimitri Van Neck and
# Michel Waroquier, Journal of Chemical Physics, Vol. 127 (16), Art. No. 164108,
# 2007
# DOI:10.1063/1.2789429
#
# "Calculating reaction rates with partial Hessians: validation of the MBH
# approach", An Ghysels, Veronique Van Speybroeck, Toon Verstraelen, Dimitri Van
# Neck and Michel Waroquier, Journal of Chemical Theory and Computation, Vol. 4
# (4), 614-625, 2008
# DOI:10.1021/ct7002836
#
# "Mobile Block Hessian approach with linked blocks: an efficient approach for
# the calculation of frequencies in macromolecules", An Ghysels, Veronique Van
# Speybroeck, Ewald Pauwels, Dimitri Van Neck, Bernard R. Brooks and Michel
# Waroquier, Journal of Chemical Theory and Computation, Vol. 5 (5), 1203-1215,
# 2009
# DOI:10.1021/ct800489r
#
# "Normal modes for large molecules with arbitrary link constraints in the
# mobile block Hessian approach", An Ghysels, Dimitri Van Neck, Bernard R.
# Brooks, Veronique Van Speybroeck and Michel Waroquier, Journal of Chemical
# Physics, Vol. 130 (18), Art. No. 084107, 2009
# DOI:10.1063/1.3071261
#
# TAMkin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>
#
# --
"""Convenient interfaces to define thermodynamic and kinetic models"""


import numpy

from molmod.units import kjmol, second, meter, mol

from tamkin.partf import compute_rate_coeff, compute_equilibrium_constant


__all__ = [
    "get_unit", "BaseModel", "ThermodynamicModel", "BaseKineticModel",
    "KineticModel", "ActivationKineticModel"
]


def get_unit(pfs_A, pfs_B, per_second=False):
    """Return the unit of the equilibrium constant or pre-exponential factor.

       Arguments:
        | pfs_A  --  The partition functions in the numerator
        | pfs_B  --  The partition functions in the denominator

       Optional argument:
        | per_second  -- Boolean, when True the unit is divided by second.
    """
    meter_power = 0
    mol_power = 0
    for pf_A in pfs_A:
        if hasattr(pf_A, "translational"):
            meter_power += pf_A.translational.dim
        mol_power += 1
    for pf_B in pfs_B:
        if hasattr(pf_B, "translational"):
            meter_power -= pf_B.translational.dim
        mol_power -= 1
    unit = meter**meter_power/mol**mol_power
    unit_name = ""
    if meter_power != 0:
        unit_name += "m**%i" % meter_power
    if mol_power != 0:
        unit_name += "*mol**%i" % mol_power
    if per_second:
        unit /= second
        unit_name += "/second"
    return unit, unit_name



class BaseModel(object):
    """Base class for all physico-chemical models."""
    def __init__(self, pfs_all):
        """
           Argument:
            | pfs_all  --  All partition functions involved in the model.

           The methods in the base class are mainly used by the Monte Carlo
           routine in the ReactionAnalysis class.
        """
        self.pfs_all = pfs_all

    def backup_freqs(self):
        """Keep a backup copy of the frequencies and the energy of each partition function."""
        for pf in self.pfs_all:
            pf.vibrational.positive_freqs_orig = pf.vibrational.positive_freqs.copy()
            pf.vibrational.negative_freqs_orig = pf.vibrational.negative_freqs.copy()
            pf.energy_backup = pf.energy

    def alter_freqs(self, freq_error, scale_energy):
        """Randomly distort the frequencies and energies.

           Arguments:
            | freq_error  --  The absolute error to be introduced in the
                              frequencies.
            | scale_energy  --  The relative error to be introduced in the
                                (electronic) energies.
        """
        for pf in self.pfs_all:
            N = len(pf.vibrational.positive_freqs)
            freq_shift = numpy.random.normal(0, freq_error, N)
            pf.vibrational.positive_freqs = pf.vibrational.positive_freqs_orig + freq_shift
            pf.vibrational.positive_freqs[pf.vibrational.positive_freqs<=0] = 0.01
            N = len(pf.vibrational.negative_freqs)
            freq_shift = numpy.random.normal(0, freq_error, N)
            pf.vibrational.negative_freqs = pf.vibrational.negative_freqs_orig + freq_shift
            pf.vibrational.negative_freqs[pf.vibrational.negative_freqs>=0] = -0.01
            pf.energy = pf.energy_backup*scale_energy

    def restore_freqs(self):
        """Restore the backup of the frequencies and the energy of each partition function."""
        for pf in self.pfs_all:
            pf.vibrational.positive_freqs = pf.vibrational.positive_freqs_orig
            pf.vibrational.negative_freqs = pf.vibrational.negative_freqs_orig
            pf.energy = pf.energy_backup
            del pf.vibrational.positive_freqs_orig
            del pf.vibrational.negative_freqs_orig
            del pf.energy_backup

    def write_to_file(self, filename):
        """Write the model to a text file.

           One argument:
            | filename  --  the file to write the output.
        """
        f = file(filename, "w")
        self.dump(f)
        f.close()

    def dump(self, f):
        """Write all info about the model to a file."""
        raise NotImplementedError


class ThermodynamicModel(BaseModel):
    """A model for a thermodynamic equilibrium."""
    def __init__(self, pfs_react, pfs_prod):
        """
           Arguments:
            | pfs_react  --  A list with reactant partition functions.
            | pfs_prod  --  A list with product partition functions.
        """
        self.pfs_react = pfs_react
        self.pfs_prod = pfs_prod
        self.unit, self.unit_name = get_unit(pfs_react, pfs_prod)
        BaseModel.__init__(self, pfs_react + pfs_prod)

    def compute_equilibrium_constant(self, temp, do_log=False):
        """Compute the equilibrium constant at the given temperature.

           Argument:
            | temp  --  The temperature.

           Optional argument:
            | do_log  --  When True, the logarithm of the equilibrium constant
                          is returned instead of just the equilibrium constant
                          itself. [default=False]
        """
        return compute_equilibrium_constant(self.pfs_react, self.pfs_prod, temp, do_log)

    def compute_reaction_free_energy(self, temp):
        """Compute the free energy difference between (+) products and (-) reactants.

           Arguments:
            | temp  --  The temperature.
        """
        return sum(pf_prod.free_energy(temp) for pf_prod in self.pfs_prod) - \
               sum(pf_react.free_energy(temp) for pf_react in self.pfs_react)

    def compute_delta_E(self):
        """Compute the classical (microscopic) energy difference between (+) products and (-) reactants."""
        return sum(pf_prod.energy for pf_prod in self.pfs_prod) - \
               sum(pf_react.energy for pf_react in self.pfs_react)

    def dump(self, f):
        """Write all info about the thermodynamic model to a file."""
        delta_E = self.compute_delta_E()
        print >> f, "Energy difference = %.1f" % (delta_E/kjmol)
        delta_A0K = self.compute_reaction_free_energy(0.0)
        print >> f, "Zero-point corrected energy difference [kJ/mol] = %.1f" % (delta_A0K/kjmol)
        print >> f
        for counter, pf_react in enumerate(self.pfs_react):
            print >> f, "Reactant %i partition function" % counter
            pf_react.dump(f)
            print >> f
        for counter, pf_prod in enumerate(self.pfs_prod):
            print >> f, "Prodcut %i partition function" % counter
            pf_prod.dump(f)
            print >> f


class BaseKineticModel(BaseModel):
    """A generic model for the rate of a chemical reaction."""
    def compute_free_energy_barrier(self, temp):
        """Compute the free energy barrier of the reaction.

           Arguments:
            | temp  -- the temperature
        """
        raise NotImplementedError

    def compute_rate_coeff(self, temp, do_log=False):
        """Compute the rate coefficient of the reaction in this analysis

           Arguments:
            | temp  -- The temperature.

           Optional argument:
            | do_log  --  When True, the logarithm of the rate coefficient is
                          returned instead of just the rate coefficient itself.
                          [default=False]
        """
        raise NotImplementedError


class KineticModel(BaseKineticModel):
    """A model for the rate of a single-step chemical reaction."""
    def __init__(self, pfs_react, pf_trans, tunneling=None):
        """
           Arguments:
            | pfs_react  --  a list of partition functions for the reactants
            | pf_trans  --  the partition function of the transition state

           Optional arguments:
            | tunneling  --  A tunneling correction object. If not given, no
                             tunneling correction is applied.


           Useful attributes:
            | unit_name  --  A string describing the conventional unit of
                             the rate coefficient
            | unit  --  The conversion factor to transform self.A into
                        conventional units (rate/self.unit)
        """
        if len(pfs_react) == 0:
            raise ValueError("At least one reactant must be given.")
        self.pfs_react = pfs_react
        self.pf_trans = pf_trans
        self.tunneling = tunneling
        self.unit, self.unit_name = get_unit(pfs_react, [pf_trans], per_second=True)
        BaseKineticModel.__init__(self, pfs_react + [pf_trans])

    def compute_rate_coeff(self, temp, do_log=False):
        """See :meth:`BaseKineticModel.compute_rate_coeff`"""
        result = compute_rate_coeff(self.pfs_react, self.pf_trans, temp, do_log)
        if self.tunneling is not None:
            if do_log:
                result += numpy.log(self.tunneling(temp))
            else:
                result *= self.tunneling(temp)
        return result

    def compute_free_energy_barrier(self, temp):
        """Compute the free energy barrier of the reaction.

           Arguments:
            | temp  -- the temperature
        """
        return self.pf_trans.free_energy(temp) - \
               sum(pf_react.free_energy(temp) for pf_react in self.pfs_react)

    def compute_delta_E(self):
        """Compute the classical (microscopic) energy barrier of the reaction."""
        return self.pf_trans.energy - \
               sum(pf_react.energy for pf_react in self.pfs_react)

    def dump(self, f):
        """Write all info about the kinetic model to a file."""
        delta_E = self.compute_delta_E()
        print >> f, "Energy barrier [kJ/mol] = %.1f" % (delta_E/kjmol)
        delta_A0K = self.compute_free_energy_barrier(0.0)
        print >> f, "Zero-point corrected energy barrier [kJ/mol] = %.1f" % (delta_A0K/kjmol)
        print >> f
        for counter, pf_react in enumerate(self.pfs_react):
            print >> f, "Reactant %i partition function" % counter
            pf_react.dump(f)
            print >> f
        print >> f, "Transition state partition function"
        self.pf_trans.dump(f)


class ActivationKineticModel(BaseKineticModel):
    """A model for the rate of a single-step chemical reaction with a pre-reactive complex."""
    def __init__(self, tm, km):
        """
           Arguments:
            | tm  --  The thermodynamic model for the pre-reactive complex.
            | km  --  The kinetic model for the single-step reaction.
        """
        self.tm = tm
        self.km = km

        # akm
        self.unit = tm.unit*km.unit
        if len(tm.pfs_react)==len(tm.pfs_prod):
            self.unit_name = km.unit_name
        elif len(tm.pfs_react)-len(tm.pfs_prod)+len(km.pfs_react)-1==0:
            self.unit_name = "1/s"
        elif len(tm.pfs_react)-len(tm.pfs_prod)+len(km.pfs_react)-1==1:
            self.unit_name = "(m**3/mol)/s"
        else:
            self.unit_name = "(m**3/mol)**%i/s" % (len(tm.pfs_react)-len(tm.pfs_prod)+len(km.pfs_react)-1)

        BaseKineticModel.__init__(self, tm.pfs_all + km.pfs_all)

    def compute_free_energy_barrier(self, temp):
        """Compute the free energy barrier of the entire reaction.

           Arguments:
            | temp  -- the temperature
        """
        return self.tm.compute_delta_free_energy(temp) + \
               self.km.compute_delta_free_energy(temp)

    def dump(self, f):
        """Write all info about the kinetic model to a file."""
        print >> f, "Thermodynamic model"
        self.tm.dump(f)
        print >> f
        print >> f, "Kinetic model"
        self.km.dump(f)

    def compute_rate_coeff(self, temp, do_log=False):
        """See :meth:`BaseKineticModel.compute_rate_coeff`"""
        if do_log:
            return self.tm.compute_equilibrium_constant(temp, True) + \
                   self.km.compute_rate_coeff(temp, True)
        else:
            return self.tm.compute_equilibrium_constant(temp, False)* \
                   self.km.compute_rate_coeff(temp, False)