#!/usr/bin/env python3

import pandas as pd
import typer
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape


def load_dfs(dir: Path):

    filenames = {
        'emissions_year': 'E_matbytech_bycountry.csv',
        'emissions_mat': 'E_matbytech_bycountry.csv',
        'jobs': 'jobs_forplot.csv',
    }
    rename_dict = {
        'KE': 'Kenya',
        'RW': 'Rwanda',
        'UG': 'Uganda',
        'UK': 'United Kingdom',
        'ZM': 'Zambia',
    }
    countries = list(rename_dict.keys())
    countries_alt = [n for n in countries if n != 'UK']

    # emissions by year
    df_ey = pd.read_csv(dir / filenames['emissions_year'], index_col=0).fillna(0)
    df_ey = df_ey.groupby(['Country', 'Scenario', 'Year']).sum().loc[countries]
    df_ey = df_ey.stack().unstack(level='Year', fill_value=0)
    df_ey.index.set_names('Mat', -1, True)

    # emissions by mat and tech
    df_et = pd.read_csv(dir / filenames['emissions_mat'], index_col=0).fillna(0).rename(columns={'tech': 'Tech'})
    df_et = df_et.groupby(['Country', 'Scenario', 'Year', 'Tech']).first().loc[countries]
    df_em = df_et.groupby(['Country', 'Scenario']).sum()
    df_et = df_et.groupby(['Country', 'Scenario', 'Tech']).sum()
    df_et = df_et.stack().unstack(level='Tech', fill_value=0)
    df_et.index.set_names('Mat', -1, True)

    # employment data
    df_j = pd.read_csv(dir / filenames['jobs'], index_col=0)
    df_j = df_j.drop(columns=['Country', 'ISO3']).rename(columns={
            'tech': 'Tech',
            'scenario': 'Scenario',
            'country': 'Country'
        })
    # drop first derivative rows
    df_j = df_j[df_j['parameter'] == 'Power Generation Capacity (Aggregate)'].drop(columns=['parameter'])
    # drop strange "Capacity" Indicator value
    df_j = df_j[df_j['Indicator'] != 'Capacity']

    df_j = df_j.groupby(['Country', 'Scenario', 'Year', 'Tech', 'Indicator']).first().loc[countries_alt]
    # only one column left, transform into series with MultiIndex, drop last index level
    df_j = df_j.stack().droplevel(-1)
    df_jyf = df_j.unstack(level='Year', fill_value=0)
    df_jy = df_j.groupby(['Country', 'Scenario', 'Year', 'Tech']).sum().unstack(level='Year', fill_value=0)

    df_jt = df_j.groupby(['Country', 'Scenario', 'Indicator', 'Tech']).sum().unstack(level='Tech', fill_value=0)
    df_ji = df_j.groupby(['Country', 'Scenario', 'Indicator']).sum().unstack(level='Indicator', fill_value=0)


    res = {
        'emissions_year': df_ey,
        'emissions_tech': df_et,
        'emissions_mat': df_em,
        'jobs_year': df_jy,
        'jobs_year_full': df_jyf,
        'jobs_tech': df_jt,
        'jobs_ind': df_ji,
    }

    for name, df in res.items():
        df.rename(index=rename_dict, inplace=True)

    return res

def df_to_dict(df, drop_full_zeros = True):
    if isinstance(df.index, pd.MultiIndex):
        return {name: df_to_dict(g.droplevel(0)) for name, g in df.groupby(level=0)}
    else:
        if drop_full_zeros:
            df = df.loc[(df!=0).any(1)]
            df = df.loc[:, (df != 0).any(axis=0)]
        # Shape of lowest level can be tuned, see:
        # https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.to_dict.html
        return df.to_dict('index')


def main(data_dir: Path = typer.Argument(..., help='An "outputs" directory containing .csv data files.'),
         input_template: Path = typer.Argument(..., help='Jinja2 template file to process.'),
         output_file: Path = typer.Argument(..., help='Location for processed template (will be overwritten).'),
         preserve_zeros: bool = False,
         verbose: bool = False):

    data_dir = data_dir.resolve()
    input_template = input_template.resolve()
    output_file = output_file.resolve()

    if verbose:
        typer.echo(f'Rendering     {input_template}\nusing data in {data_dir}\nand saving to {output_file}')

    env = Environment(
        loader=FileSystemLoader(input_template.parent),
        autoescape=select_autoescape(['html', 'xml'])
    )
    template = env.get_template(input_template.name)

    dfs = load_dfs(data_dir)

    if verbose:
        for name, df in dfs.items():
            typer.echo(f'DataFrame {name}:')
            typer.echo(df)

    # don't use json.dumps, instead rely on Jinja doing the right thing
    stream = template.stream(**{name: df_to_dict(df, not preserve_zeros) for name, df in dfs.items()})
    with output_file.open('w') as file:
        stream.dump(file)

if __name__ == '__main__':
    typer.run(main)
