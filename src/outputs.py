import csv
import logging
import datetime as dt

from prettytable import PrettyTable
from functools import partial
from constants import BASE_DIR, DATETIME_FORMAT


def default_output(results):
    for row in results:
        print(*row)


def pretty_output(results):
    table = PrettyTable()
    table.field_names = results[0]
    table.align = 'l'
    table.add_rows(results[1:])
    print(table)


def file_output(results, cli_args):
    RESULT_DIR = BASE_DIR / 'results'
    RESULT_DIR.mkdir(exist_ok=True)
    now_formatted = dt.datetime.now().strftime(DATETIME_FORMAT)
    file_name = f'{cli_args.mode}_{now_formatted}.csv'
    FILE_PATH = RESULT_DIR / file_name
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        writer = csv.writer(f, dialect='unix')
        writer.writerows(results)
    logging.info(f'Файл с результатами был сохранён: {FILE_PATH}')


def control_output(results, cli_args):
    output_functions = {
        'pretty': pretty_output,
        'file': partial(file_output, cli_args=cli_args),
        None: default_output,
    }
    output_functions[cli_args.output](results)
