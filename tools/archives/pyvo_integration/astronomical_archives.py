import sys
import os

import pyvo
from pyvo import registry

import urllib
from urllib import parse, request



class Service:

    # https://pyvo.readthedocs.io/en/latest/api/pyvo.registry.Servicetype.html

    services = {
        'TAP': 'tap',
        'SIA': 'sia',
        'SIA2': 'sia2',
        'SPECTRUM': 'spectrum',
        'SCS': 'scs',
        'LINE': 'line'
    }

    supported_services = {
        'TAP': 'tap'
    }

    def __init__(self):
        pass

    @staticmethod
    def is_service_supported(service_type) -> bool:
        is_supported = True

        if service_type not in Service.services.keys():
            is_supported = False
        elif service_type not in Service.supported_services.keys():
            is_supported = False

        return is_supported


class Waveband:

    # https://pyvo.readthedocs.io/en/latest/api/pyvo.registry.Waveband.html
    # https://www.ivoa.net/rdf/messenger/2020-08-26/messenger.html

    wavebands = {
        'Extreme UV': 'EUV',
        'Gamma ray': 'Gamma-ray',
        'Infrared': 'Infrared',
        'Millimeter': 'Millimeter',
        'Neutrino': 'Neutrino',
        'Optical': 'Optical',
        'Photon': 'Photon',
        'Radio': 'Radio',
        'Ultra violet': 'UV',
        'X-ray': 'X-ray'
    }

    def __init__(self):
        pass

    @staticmethod
    def is_waveband_supported(waveband) -> bool:
        is_supported = True

        if waveband not in Waveband.wavebands.keys():
            is_supported = False

        return is_supported


class TapArchive:

    # https://www.ivoa.net/documents/ObsCore/20170509/REC-ObsCore-v1.1-20170509

    service_type = Service.services['TAP']

    def __init__(self, id, title, name, access_url):
        self.id = id,
        self.title = title,
        self.name = name,
        self.access_url = access_url
        self.initialized = False
        self.archive_service = None
        self.tables = None

    def get_resources(self, query, number_of_results, url_field='access_url'):
        resource_list = []

        if self.initialized:

            try:
                raw_resource_list = self.archive_service.search(query)

                for i, resource in enumerate(raw_resource_list):
                    if i < number_of_results:
                        resource_list.append(resource[url_field])
            except Exception as e:
                pass

        return resource_list

    def initialize(self):
        self._get_service()

        if self.archive_service:
            self._set_archive_tables()
            self.initialized = True

    def _get_service(self):
        if self.access_url:
            self.archive_service = pyvo.dal.TAPService(self.access_url)

    def _set_archive_tables(self):

        self.tables = []

        for table in self.archive_service.tables:
            archive_table = {
                'name': table.name,
                'type': table.type,
                'fields': None
            }

            fields = []

            for table_field in table.columns:
                field = {
                    'name': table_field.name,
                    'description': table_field.description,
                    'unit': table_field.unit,
                    'datatype': table_field.datatype.content
                }

                fields.append(field)

            archive_table['fields'] = fields

            self.tables.append(archive_table)

    def _is_query_valid(self, query) -> bool:
        is_valid = True

        attribute_from = 'from'
        attribute_where = 'where'

        idx_from = query.index(attribute_from)
        idx_where = query.index(attribute_where)

        table_name = ''

        for idx in range(idx_from + len('from') + 1, idx_where):
            table_name = table_name + query[idx]

        if table_name not in self.tables.values():
            is_valid = False

        return is_valid


class RegistrySearchParameters:

    def __init__(self, keyword=None, waveband=None, service_type=None):
        self.keyword = keyword
        self.waveband = waveband
        self.service_type = service_type

    def get_parameters(self):

        parameters = {
            'keywords': '',
            'waveband': '',
            'service_type': ''
        }

        if self.keyword:
            parameters['keywords'] = self.keyword

        if Waveband.is_waveband_supported(self.waveband):
            parameters['waveband'] = Waveband.wavebands[self.waveband]

        if Service.is_service_supported(self.service_type):
            parameters['service_type'] = Service.services[self.service_type]
        else:
            parameters['service_type'] = Service.services['TAP']

        return parameters


class Registry:

    def __init__(self):
        pass

    @staticmethod
    def search_registries(rsp: RegistrySearchParameters, number_of_registries):

        parameters = rsp.get_parameters()

        keywords = parameters['keywords']
        waveband = parameters['waveband']
        service_type = parameters['service_type']

        registry_list = []

        if not waveband:
            registry_list = registry.search(keywords=keywords, servicetype=service_type)
        else:
            registry_list = registry.search(keywords=keywords, waveband=waveband, servicetype=service_type)

        if registry_list:
            registry_list = Registry._get_registries_from_list(registry_list, 1)

        return registry_list

    @staticmethod
    def _get_registries_from_list(registry_list, number_of_registries):

        archive_list = []

        for i, registry in enumerate(registry_list):
            if i < number_of_registries:
                archive = TapArchive(registry.standard_id, registry.res_title, registry.short_name, registry.access_url)
                archive_list.append(archive)

        return archive_list


class TapQuery:

    def __init__(self, query):
        self.raw_query = query

    def get_query(self):
        return urllib.parse.unquote(self.raw_query).replace("+", " ")


class BaseADQLQuery:

    def __init__(self):
        pass

    def _get_order_by_clause(self, order_type):
        order_by_clause = 'ORDER BY ' + order_type

        return order_by_clause

    def _get_where_clause(self, parameters):
        where_clause = ''
        is_first_statement = True

        for key, value in parameters.items():
            statement = ''

            if value != '':
                statement = str(key) + ' = ' + '\'' + str(value) + '\' '

                if is_first_statement:
                    is_first_statement = False
                    where_clause += 'WHERE '
                else:
                    statement = 'AND ' + statement

                where_clause += statement

        return where_clause


class ADQLObscoreQuery(BaseADQLQuery):

    order_by_field = {
        'size': 'access_estsize',
        'collection': 'obs_collection',
        'object': 'target_name'
    }

    base_query = 'SELECT TOP 100 * FROM ivoa.obscore '

    def __init__(self,
                 dataproduct_type,
                 obs_collection,
                 facility_name,
                 instrument_name,
                 em_min,
                 em_max,
                 target_name,
                 obs_publisher_id,
                 s_fov,
                 calibration_level,
                 order_by):

        super().__init__()

        if calibration_level == 'none':
            calibration_level = ''

        if order_by == 'none':
            order_by = ''

        self.parameters = {
            'dataproduct_type': dataproduct_type,
            'obs_collection': obs_collection,
            'facility_name': facility_name,
            'instrument_name': instrument_name,
            'em_min': em_min,
            'em_max': em_max,
            'target_name': target_name,
            'obs_publisher_id': obs_publisher_id,
            's_fov': s_fov,
            'calibration_level': calibration_level
        }

        self.order_by = order_by

    def get_query(self):
        return ADQLObscoreQuery.base_query + self.get_where_statement() + self.get_order_by_statement()

    def get_order_by_statement(self):
        if self.order_by != '':
            return self._get_order_by_clause(self.order_by)
        else:
            return ''

    def _get_order_by_clause(self, order_type):

        obscore_order_type = ADQLObscoreQuery.order_by_field[order_type]

        return super()._get_order_by_clause(obscore_order_type)

    def get_where_statement(self):
        return self._get_where_clause(self.parameters)

    def _get_where_clause(self, parameters):
        return super()._get_where_clause(parameters)


class ADQLTapQuery(BaseADQLQuery):

    base_query = 'SELECT TOP 100 * FROM '

    def __init__(self):
        super().__init__()

    def get_order_by_clause(self, order_type):
        return super().get_order_by_clause(order_type)

    def get_query(self, table, where_field, where_condition):
        return ADQLTapQuery.base_query + str(table) + ' WHERE ' + str(where_field) + ' = ' + '\''+str(where_condition)+'\''


class FileHandler:

    def __init__(self):
        pass

    @staticmethod
    def download_file_from_url(file_url):
        with request.urlopen(file_url) as response:
            fits_file = response.read()

        return fits_file

    @staticmethod
    def write_file_to_output(file, output):
        with open(output, "w") as file_output:
            file_output.write(file)

    @staticmethod
    def write_urls_to_output(urls: [], output):
        with open(output, "w") as file_output:
            for url in urls:
                file_output.write(url+',')

    @staticmethod
    def write_multiple_outputs(output_id):

        out_files = {}

        for i in range(1, 10):
            out_files[i] = open(
                os.path.join(database_tmp_dir, "primary_%s_%s_visible_interval_%s" % (output_id, i, i)), "w+"
            )
            out_files[i].write("aaaaa")

        for file_out in out_files.values():
            file_out.close()

    @staticmethod
    def write_collection(output):
        dir = os.getcwd()

        dir += '/fits'

        upload_dir = os.path.join(dir, 'aaaaa.fits')

        with open(output, "w") as file_output:
            file_output.write(upload_dir)

    @staticmethod
    def write_collection1(index):
        dir = os.getcwd()

        dir += '/fits'

        upload_dir = os.path.join(dir, index + '.fits')

        with open(upload_dir, "w") as file_output:
            file_output.write(upload_dir)

    @staticmethod
    def write_file_to_subdir(file, index):
        dir = os.getcwd()

        dir += '/fits'

        upload_dir = os.path.join(dir, str(index) + '.fits')

        with open(upload_dir, "wb") as file_output:
            file_output.write(file)
    @staticmethod
    def get_file_name_from_url(url, index=None):
        url_parts = url.split('/')

        file_name = 'archive file '

        try:

            if(url_parts[-1]) != '':
                file_name = url_parts[-1]
            elif len(url_parts) > 1:
                file_name = url_parts[-2]
        except Exception:
            pass

        return file_name


if __name__ == "__main__":

    output = sys.argv[1]
    download_type = sys.argv[2]
    number_of_files = sys.argv[3]
    archive_type = sys.argv[4]

    file_url = []

    if archive_type == 'registry':

        keyword = sys.argv[5]
        waveband = sys.argv[6]
        service_type = sys.argv[7]
        query_type = sys.argv[8]

        if query_type == 'obscore_query':

            dataproduct_type = sys.argv[9]
            obs_collection = sys.argv[10]
            facility_name = sys.argv[11]
            instrument_name = sys.argv[12]
            em_min = sys.argv[13]
            em_max = sys.argv[14]
            target_name = sys.argv[15]
            obs_publisher_id = sys.argv[16]
            s_fov = sys.argv[17]
            calibration_level = sys.argv[18]
            order_by = sys.argv[19]

            obscore_query_object = ADQLObscoreQuery(dataproduct_type,
                                                  obs_collection,
                                                  facility_name,
                                                  instrument_name,
                                                  em_min,
                                                  em_max,
                                                  target_name,
                                                  obs_publisher_id,
                                                  s_fov,
                                                  calibration_level,
                                                  order_by)

            adql_query = obscore_query_object.get_query()

        elif query_type == 'raw_query':
            tap_table = sys.argv[9]
            where_field = sys.argv[10]
            where_condition = sys.argv[11]
            url_field = sys.argv[12]

            adql_query = ADQLTapQuery().get_query(tap_table, where_field, where_condition)

        else:
            adql_query = ADQLObscoreQuery.base_query

        rsp = RegistrySearchParameters(keyword=keyword, waveband=waveband, service_type=service_type)

        archive_list = Registry.search_registries(rsp, 1)

        archive_list[0].initialize()

        if query_type == 'raw_query':
            file_url = archive_list[0].get_resources(adql_query, int(number_of_files), url_field)
        else:
            file_url = archive_list[0].get_resources(adql_query, int(number_of_files))

    elif archive_type == 'archive':

        service_url = sys.argv[5]

        query_type = sys.argv[6]

        if query_type == 'obscore_query':

            dataproduct_type = sys.argv[7]
            obs_collection = sys.argv[8]
            facility_name = sys.argv[9]
            instrument_name = sys.argv[10]
            em_min = sys.argv[11]
            em_max = sys.argv[12]
            target_name = sys.argv[13]
            obs_publisher_id = sys.argv[14]
            s_fov = sys.argv[15]
            calibration_level = sys.argv[16]
            order_by = sys.argv[17]

            obscore_query_object = ADQLObscoreQuery(dataproduct_type,
                                                  obs_collection,
                                                  facility_name,
                                                  instrument_name,
                                                  em_min,
                                                  em_max,
                                                  target_name,
                                                  obs_publisher_id,
                                                  s_fov,
                                                  calibration_level,
                                                  order_by)

            adql_query = obscore_query_object.get_query()

        elif query_type == 'raw_query':

            tap_table = sys.argv[7]
            where_field = sys.argv[8]
            where_condition = sys.argv[9]
            url_field = sys.argv[10]

            adql_query = ADQLTapQuery().get_query(tap_table, where_field, where_condition)

        else:
            adql_query = ADQLObscoreQuery.base_query

        archive = TapArchive(1, 'name', 'title', service_url)

        archive.initialize()

        if query_type == 'raw_query':
            file_url = archive.get_resources(adql_query, int(number_of_files), url_field)
        else:
            file_url = archive.get_resources(adql_query, int(number_of_files))

    if file_url and download_type == 'urls':

        FileHandler.write_urls_to_output(file_url, output)

    elif file_url and download_type == 'files':

        FileHandler.write_urls_to_output(file_url, output)

        for i, url in enumerate(file_url):
            try:
                fits_file = FileHandler.download_file_from_url(url.rstrip(','))
                FileHandler.write_file_to_subdir(fits_file, FileHandler.get_file_name_from_url(url.rstrip(',')))
            except Exception as e:
                pass
    else:
        fits_file = 'No files matching parameters'
        FileHandler.write_file_to_output(fits_file, output)