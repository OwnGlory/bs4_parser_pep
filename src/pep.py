import re
import logging
import requests_cache

from tqdm import tqdm
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from utils import get_response, find_tag

PEP_LIST_URL = 'https://peps.python.org/'

COUNT_STATUS = {
    'Active': 0,
    'Accepted': 0,
    'Deferred': 0,
    'Final': 0,
    'Provisional': 0,
    'Rejected': 0,
    'Superseded': 0,
    'Withdrawn': 0,
    'Draft': 0,
}

SECTIONS_ID = ['index-by-category', 'numerical-index', 'reserved-pep-numbers']


def get_pep_info():
    total_number_pep = 0
    session = requests_cache.CachedSession()
    # session.cache.clear()
    response = get_response(session, PEP_LIST_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    results = [('Статус', 'Количество')]
    for section_id in SECTIONS_ID:
        main_section = find_tag(soup, 'section', attrs={'id': section_id})
        section_with_tbody = main_section.find_all('tbody')
        for tbody in section_with_tbody:
            sections_by_python = tbody.find_all('tr')
            for section in tqdm(sections_by_python):
                type_and_status_pep = find_tag(
                        section, 'abbr'
                    )
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
                    if detail_status_pep in COUNT_STATUS:
                        total_number_pep += 1
                        COUNT_STATUS[detail_status_pep] += 1
                    else:
                        logging.info("Найден неизвестный статус!")

                if main_status_pep != detail_status_pep:
                    logging.info(
                       f"Несовпадающие статусы:\n {version_link}"
                       f"Статус в карточке: {main_status_pep}"
                       f"Ожидаемые статусы: ['{detail_type_pep}',\
                        '{detail_status_pep}']"
                    )
    for key, item in COUNT_STATUS.items():
        results.append((key, item))
    results.append(('Total', total_number_pep))
    print(results)


MODE_TO_FUNCTION = {
    'get_pep_info': get_pep_info,
}


def main():
    get_pep_info()


if __name__ == "__main__":
    main()
