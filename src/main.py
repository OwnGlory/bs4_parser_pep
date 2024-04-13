import re
import logging
import requests_cache

from urllib.parse import urljoin
from bs4 import BeautifulSoup
from tqdm import tqdm
from constants import (
    BASE_DIR,
    MAIN_DOC_URL,
    PEP_LIST_URL,
    EXPECTED_STATUS,
    SECTIONS_ID
)
from outputs import control_output
from configs import configure_argument_parser, configure_logging
from utils import get_response
from exceptions import VersionsNotFoundError


def whats_new(session):
    response = get_response(
        session,
        urljoin(MAIN_DOC_URL, 'whatsnew/')
    )
    if response is None:
        return

    soup = BeautifulSoup(response.text, features='lxml')
    sections_by_python = soup.select(
        'section#what-s-new-in-python div.toctree-wrapper li.toctree-l1'
    )

    for section in tqdm(sections_by_python):
        version_link = urljoin(
            urljoin(MAIN_DOC_URL, 'whatsnew/'),
            section.select_one('a')['href']
        )
        print(version_link)

    results = [('Ссылка на статью', 'Заголовок', 'Редактор, Автор')]
    for section in tqdm(sections_by_python):
        version_link = urljoin(
            urljoin(MAIN_DOC_URL, 'whatsnew/'),
            section.select_one('a')['href']
        )
        response = get_response(session, version_link)
        if response is None:
            continue
        soup = BeautifulSoup(response.text, features='lxml')
        results.append((
            version_link,
            soup.select_one('h1').text,
            soup.select_one('dl').text.replace('\n', ' ')
        ))

    return results


def latest_versions(session):
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return

    soup = BeautifulSoup(response.text, 'lxml')
    a_tags = soup.select('div.sphinxsidebarwrapper ul a')

    if not a_tags:
        raise VersionsNotFoundError('Не найден список c версиями Python')

    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    for a_tag in a_tags:
        text_match = re.search(
            r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)',
            a_tag.text
        )
        if text_match is not None:
            version, status = text_match.groups()
        else:
            version, status = a_tag.text, ''
        results.append(
            (a_tag['href'], version, status)
        )

    return results


def download(session):
    response = get_response(session, urljoin(MAIN_DOC_URL, 'download.html'))
    if response is None:
        return

    soup = BeautifulSoup(response.text, 'lxml')
    pdf_a4_tag = soup.select_one(
        'div[role="main"] table.docutils a[href$="pdf-a4.zip"]'
    )

    archive_url = urljoin(MAIN_DOC_URL, pdf_a4_tag['href'])
    filename = archive_url.split('/')[-1]
    DOWNLOADS_DIR = BASE_DIR / 'downloads'
    DOWNLOADS_DIR.mkdir(exist_ok=True)
    ARCHIVE_PATH = DOWNLOADS_DIR / filename
    response = session.get(archive_url)
    with open(ARCHIVE_PATH, 'wb') as file:
        file.write(response.content)
    logging.info(f'Архив был загружен и сохранён: {ARCHIVE_PATH}')


def get_type_and_status(section):
    type_and_status_pep = section.select_one('abbr')
    if type_and_status_pep is not None:
        type_and_status_pep = type_and_status_pep['title'].split(', ')
        if len(type_and_status_pep) == 1:
            main_status_pep = ''
        else:
            main_status_pep = type_and_status_pep[1]
    else:
        main_status_pep = ''
    return main_status_pep


def get_detail_status(detail_section_with_dl):
    pattern = (
        r'<dt class="field-\w+">(Status|Type)'
        r'<span class="colon">:<\/span><\/dt>\s*'
        r'<dd class="field-\w+">'
        r'<abbr title=".*?">(.*?)<\/abbr><\/dd>'
    )
    matches = re.findall(pattern, str(detail_section_with_dl), re.DOTALL)
    if matches is not None:
        return matches[0][1], matches[1][1]
    else:
        return None, None


def get_table_from_section(session, section_with_tbody):
    number_pep = 0
    for tbody in section_with_tbody:
        sections_by_python = tbody.select('tr')
        for section in tqdm(sections_by_python):
            main_status_pep = get_type_and_status(section)
            version_link = urljoin(
                PEP_LIST_URL,
                section.select_one('a')['href']
            )
            response = get_response(session, version_link)
            detail_soup = BeautifulSoup(response.text, features='lxml')
            detail_section = detail_soup.select_one('section#pep-content')
            detail_section_with_dl = detail_section.select_one(
                'dl.rfc2822.field-list.simple'
            )
            detail_status_pep, detail_type_pep = get_detail_status(
                detail_section_with_dl
            )
            if detail_status_pep in EXPECTED_STATUS:
                number_pep += 1
                EXPECTED_STATUS[detail_status_pep] += 1
            else:
                logging.info("Найден неизвестный статус!")
            if main_status_pep != detail_status_pep:
                logging.info(
                   f"Несовпадающие статусы:\n{version_link}"
                   f"\nСтатус в карточке: {main_status_pep}"
                   f"\nОжидаемые статусы: ['{detail_type_pep}',"
                   f" {detail_status_pep}']"
                )
    return number_pep


def pep(session):
    total_number_pep = 0
    response = get_response(session, PEP_LIST_URL)
    if response is None:
        return
    results = [('Статус', 'Количество')]
    soup = BeautifulSoup(response.text, features='lxml')
    for section_id in SECTIONS_ID:
        main_section = soup.select_one(f'section#{section_id}')
        total_number_pep += get_table_from_section(
            session,
            main_section.select('tbody')
        )
    for key, item in EXPECTED_STATUS.items():
        results.append((key, item))
    results.append(('Total', total_number_pep))
    return results


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep,
}


def main():
    configure_logging()
    logging.info('Парсер запущен!')

    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    logging.info(f'Аргументы командной строки: {args}')

    session = requests_cache.CachedSession()
    if args.clear_cache:
        session.cache.clear()

    results = MODE_TO_FUNCTION[args.mode](session)

    if results is not None:
        control_output(results, args)
    logging.info('Парсер завершил работу.')


if __name__ == '__main__':
    main()
