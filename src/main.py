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
from utils import get_response, find_tag


def whats_new(session):
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    response = get_response(session, whats_new_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})
    sections_by_python = div_with_ul.find_all(
        'li',
        attrs={'class': 'toctree-l1'}
    )

    for section in tqdm(sections_by_python):
        version_a_tag = find_tag(section, 'a')
        href = version_a_tag['href']
        version_link = urljoin(whats_new_url, href)
        print(version_link)

    results = [('Ссылка на статью', 'Заголовок', 'Редактор, Автор')]
    for section in tqdm(sections_by_python):
        version_a_tag = find_tag(section, 'a')
        href = version_a_tag['href']
        version_link = urljoin(whats_new_url, href)
        response = get_response(session, version_link)
        if response is None:
            continue
        soup = BeautifulSoup(response.text, features='lxml')
        h1 = find_tag(soup, 'h1')
        dl = find_tag(soup, 'dl')
        dl_text = dl.text.replace('\n', ' ')
        results.append((version_link, h1, dl_text))

    return results


def latest_versions(session):
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, 'lxml')
    sidebar = find_tag(soup, 'div', {'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')
    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise Exception('Не найден список c версиями Python')

    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    for a_tag in a_tags:
        link = a_tag['href']
        text_match = re.search(pattern, a_tag.text)
        if text_match is not None:
            version, status = text_match.groups()
        else:
            version, status = a_tag.text, ''
        results.append(
            (link, version, status)
        )

    return results


def download(session):
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    response = get_response(session, downloads_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, 'lxml')
    main_tag = find_tag(soup, 'div', {'role': 'main'})
    table_tag = find_tag(main_tag, 'table', {'class': 'docutils'})
    pdf_a4_tag = find_tag(
        table_tag,
        'a',
        {'href': re.compile(r'.+pdf-a4\.zip$')}
    )
    pdf_a4_link = pdf_a4_tag['href']
    archive_url = urljoin(downloads_url, pdf_a4_link)
    filename = archive_url.split('/')[-1]
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename
    response = session.get(archive_url)
    with open(archive_path, 'wb') as file:
        file.write(response.content)
    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def get_table_from_section(session, section_with_tbody):
    number_pep = 0
    for tbody in section_with_tbody:
        sections_by_python = tbody.find_all('tr')
        for section in tqdm(sections_by_python):
            try:
                type_and_status_pep = find_tag(
                    section, 'abbr'
                )
            except Exception:
                type_and_status_pep = []
            if type_and_status_pep != []:
                type_and_status_pep = type_and_status_pep['title'].split(
                    ', '
                )
                if len(type_and_status_pep) == 1:
                    main_status_pep = ''
                else:
                    main_status_pep = type_and_status_pep[1]
            else:
                main_status_pep = ''
            href = find_tag(section, 'a')['href']
            version_link = urljoin(PEP_LIST_URL, href)
            response = get_response(session, version_link)
            detail_soup = BeautifulSoup(response.text, features='lxml')
            detail_section = find_tag(
                detail_soup, 'section',
                attrs={'id': 'pep-content'}
            )
            detail_section_with_dl = find_tag(
                detail_section, 'dl',
                attrs={'class': 'rfc2822 field-list simple'}
            )
            pattern = (
                r'<dt class="field-\w+">(Status|Type)'
                r'<span class="colon">:<\/span><\/dt>\s*'
                r'<dd class="field-\w+">'
                r'<abbr title=".*?">(.*?)<\/abbr><\/dd>'
            )
            matches = re.findall(
                pattern, str(detail_section_with_dl),
                re.DOTALL
            )
            if matches is not None:
                detail_status_pep = matches[0][1]
                detail_type_pep = matches[1][1]
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
    soup = BeautifulSoup(response.text, features='lxml')
    results = [('Статус', 'Количество')]
    for section_id in SECTIONS_ID:
        main_section = find_tag(soup, 'section', attrs={'id': section_id})
        section_with_tbody = main_section.find_all('tbody')
        total_number_pep += get_table_from_section(session, section_with_tbody)
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

    parser_mode = args.mode
    results = MODE_TO_FUNCTION[parser_mode](session)

    if results is not None:
        control_output(results, args)
    logging.info('Парсер завершил работу.')


if __name__ == '__main__':
    main()
