import pytest
import pandas as pd
from pandas.util.testing import assert_series_equal
from astropy import units as u
from numpy.testing import assert_almost_equal
from sqlalchemy import and_
from sqlalchemy.orm import joinedload
from carsus.model import Ion, Atom, DataSource, IonizationEnergy
from carsus.io.nist.ionization import download_ionization_energies, NISTIonizationEnergiesParser,\
    NISTIonizationEnergiesIngester


test_data = """
<h2> Be specta </h2>
<pre>
--------------------------------------------------------------------------------------------
At. num | Ion Charge | Ground Shells | Ground Level |      Ionization Energy (a) (eV)      |
--------|------------|---------------|--------------|--------------------------------------|
      4 |          0 | 1s2.2s2       | 1S0          |                 9.3226990(70)        |
      4 |         +1 | 1s2.2s        | 2S<1/2>      |                18.211153(40)         |
      4 |         +2 | 1s2           | 1S0          |   <a class=bal>[</a>153.8961980(40)<a class=bal>]</a>       |
      4 |         +3 | 1s            | 2S<1/2>      |   <a class=bal>(</a>217.7185766(10)<a class=bal>)</a>       |
--------------------------------------------------------------------------------------------
</pre>
"""

expected_at_num = [4, 4, 4, 4]

expected_ion_charge = [0, 1, 2, 3]

expected_indices = zip(expected_at_num, expected_ion_charge)

expected_ground_shells = ('ground_shells',
                          ['1s2.2s2', '1s2.2s', '1s2', '1s']
                          )

expected_ground_level = ('ground_level',
                         ['1S0', '2S<1/2>', '1S0', '2S<1/2>']
                         )

expected_ioniz_energy_value = ('ionization_energy_value',
                               [9.3226990, 18.211153, 153.8961980, 217.7185766]
                               )

expected_ioniz_energy_uncert = ('ionization_energy_uncert',
                                [7e-6, 4e-5, 4e-6, 1e-6]
                                )

expected_ioniz_energy_method = ('ionization_energy_method',
                                ['meas', 'meas', 'intrpl', 'theor']
                                )


@pytest.fixture
def ioniz_energies_parser():
    parser = NISTIonizationEnergiesParser(input_data=test_data)
    return parser


@pytest.fixture
def ioniz_energies_df(ioniz_energies_parser):
    return ioniz_energies_parser.prepare_ioniz_energies_df()


@pytest.fixture
def ioniz_energies_ingester(memory_session):
    ingester = NISTIonizationEnergiesIngester(memory_session)
    ingester.parser(test_data)
    return ingester

@pytest.fixture(params=[expected_ground_shells,
                        expected_ground_level, expected_ioniz_energy_value,
                        expected_ioniz_energy_uncert, expected_ioniz_energy_method])
def expected_series(request):
    index = pd.MultiIndex.from_tuples(tuples=expected_indices,
                                       names=['atomic_number', 'ion_charge'])
    name, data = request.param
    return pd.Series(data=data, name=name, index=index)


def test_prepare_ioniz_energies_df_null_values(ioniz_energies_df):
    assert all(pd.notnull(ioniz_energies_df["ionization_energy_value"]))


def test_prepare_ioniz_energies_df(ioniz_energies_df, expected_series):
    series = ioniz_energies_df[expected_series.name]
    assert_series_equal(series, expected_series)


@pytest.mark.parametrize("index, value, uncert",
                         zip(expected_indices,
                             expected_ioniz_energy_value[1],
                             expected_ioniz_energy_uncert[1]))
def test_ingest_test_data(index, value, uncert, memory_session, ioniz_energies_ingester):

    ioniz_energies_ingester.ingest()

    atomic_number, ion_charge = index
    ion = memory_session.query(Ion).options(joinedload('ionization_energies')).get((atomic_number, ion_charge))

    ion_energy = ion.ionization_energies[0]
    assert_almost_equal(ion_energy.quantity.value, value)
    assert_almost_equal(ion_energy.uncert, uncert)


@pytest.mark.remote_data
def test_ingest_nist_asd_ion_data(memory_session):
    ingester = NISTIonizationEnergiesIngester(memory_session)
    ingester.download('h-uuh')
    ingester.ingest()