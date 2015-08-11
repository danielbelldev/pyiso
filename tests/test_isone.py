from pyiso import client_factory
from unittest import TestCase
from datetime import datetime, timedelta
import pytz
import logging
import dateutil.parser


class TestISONE(TestCase):
    def setUp(self):
        self.c = client_factory('ISONE')
        handler = logging.StreamHandler()
        self.c.logger.addHandler(handler)
        self.c.logger.setLevel(logging.INFO)

    def test_auth(self):
        """Auth info should be set up from env during init"""
        self.assertEqual(len(self.c.auth), 2)

    def test_utcify(self):
        ts_str = '2014-05-03T02:32:44.000-04:00'
        ts = self.c.utcify(ts_str)
        self.assertEqual(ts.year, 2014)
        self.assertEqual(ts.month, 5)
        self.assertEqual(ts.day, 3)
        self.assertEqual(ts.hour, 2+4)
        self.assertEqual(ts.minute, 32)
        self.assertEqual(ts.second, 44)
        self.assertEqual(ts.tzinfo, pytz.utc)

    def test_handle_options_gen_latest(self):
        self.c.handle_options(data='gen', latest=True)
        self.assertEqual(self.c.options['market'], self.c.MARKET_CHOICES.na)
        self.assertEqual(self.c.options['frequency'], self.c.FREQUENCY_CHOICES.na)

    def test_handle_options_load_latest(self):
        self.c.handle_options(data='load', latest=True)
        self.assertEqual(self.c.options['market'], self.c.MARKET_CHOICES.fivemin)
        self.assertEqual(self.c.options['frequency'], self.c.FREQUENCY_CHOICES.fivemin)

    def test_handle_options_load_forecast(self):
        self.c.handle_options(data='load', forecast=True)
        self.assertEqual(self.c.options['market'], self.c.MARKET_CHOICES.dam)
        self.assertEqual(self.c.options['frequency'], self.c.FREQUENCY_CHOICES.dam)

    def test_endpoints_gen_latest(self):
        self.c.handle_options(data='gen', latest=True)
        endpoints = self.c.request_endpoints()
        self.assertEqual(len(endpoints), 1)
        self.assertIn('/genfuelmix/current.json', endpoints)

    def test_endpoints_load_latest(self):
        self.c.handle_options(data='load', latest=True)
        endpoints = self.c.request_endpoints()
        self.assertEqual(len(endpoints), 1)
        self.assertIn('/fiveminutesystemload/current.json', endpoints)

    def test_endpoints_load_forecast(self):
        self.c.handle_options(data='load', forecast=True)
        endpoints = self.c.request_endpoints()
        self.assertEqual(len(endpoints), 3)
        self.assertIn('/hourlyloadforecast/day/', endpoints[0])

        now = pytz.utc.localize(datetime.utcnow())
        date_str = now.strftime('%Y%m%d')
        self.assertIn(date_str, endpoints[0])

    def test_genmix_json_format(self):
        data = self.c.fetch_data('/genfuelmix/current.json', self.c.auth)

        # one item, GenFuelMixes
        self.assertIn('GenFuelMixes', data.keys())
        self.assertEqual(len(data.keys()), 1)

        # one item, GenFuelMix
        self.assertIn('GenFuelMix', data['GenFuelMixes'].keys())
        self.assertEqual(len(data['GenFuelMixes'].keys()), 1)

        # multiple items
        self.assertGreater(len(data['GenFuelMixes']['GenFuelMix']), 1)
        self.assertEqual(sorted(data['GenFuelMixes']['GenFuelMix'][0].keys()),
                         sorted(['FuelCategory', 'BeginDate', 'MarginalFlag', 'FuelCategoryRollup', 'GenMw']))

    def test_load_realtime_json_format(self):
        data = self.c.fetch_data('/fiveminutesystemload/current.json', self.c.auth)

        # one item, FiveMinSystemLoad
        self.assertIn('FiveMinSystemLoad', data.keys())
        self.assertEqual(len(data.keys()), 1)

        # several items, including date and load
        self.assertEqual(len(data['FiveMinSystemLoad']), 1)
        self.assertIn('BeginDate', data['FiveMinSystemLoad'][0].keys())
        self.assertIn('LoadMw', data['FiveMinSystemLoad'][0].keys())

        # values
        date = dateutil.parser.parse(data['FiveMinSystemLoad'][0]['BeginDate'])
        now = pytz.utc.localize(datetime.utcnow())
        self.assertLessEqual(date, now)
        self.assertGreaterEqual(date, now - timedelta(minutes=6))
        self.assertEqual(date.minute % 5, 0)
        self.assertGreater(data['FiveMinSystemLoad'][0]['LoadMw'], 0)

    def test_load_past_json_format(self):
        data = self.c.fetch_data('/fiveminutesystemload/day/20150610.json', self.c.auth)

        # one item, FiveMinSystemLoads
        self.assertIn('FiveMinSystemLoads', data.keys())
        self.assertEqual(len(data.keys()), 1)
        self.assertIn('FiveMinSystemLoad', data['FiveMinSystemLoads'].keys())
        self.assertEqual(len(data['FiveMinSystemLoads'].keys()), 1)

        # 288 elements: every 5 min
        self.assertEqual(len(data['FiveMinSystemLoads']['FiveMinSystemLoad']), 288)

        # several items, including date and load
        self.assertIn('BeginDate', data['FiveMinSystemLoads']['FiveMinSystemLoad'][0].keys())
        self.assertIn('LoadMw', data['FiveMinSystemLoads']['FiveMinSystemLoad'][0].keys())

    def test_load_forecast_json_format(self):
        # two days in future
        day_after_tomorrow = pytz.utc.localize(datetime.utcnow()) + timedelta(days=2)
        date_str = day_after_tomorrow.strftime('%Y%m%d')
        data = self.c.fetch_data('/hourlyloadforecast/day/%s.json' % date_str, self.c.auth)

        # one item, u'HourlyLoadForecasts
        self.assertIn('HourlyLoadForecasts', data.keys())
        self.assertEqual(len(data.keys()), 1)
        self.assertIn('HourlyLoadForecast', data['HourlyLoadForecasts'].keys())
        self.assertEqual(len(data['HourlyLoadForecasts'].keys()), 1)

        # 24 elements: every 1 hr
        self.assertEqual(len(data['HourlyLoadForecasts']['HourlyLoadForecast']), 24)

        # several items, including date and load
        self.assertIn('BeginDate', data['HourlyLoadForecasts']['HourlyLoadForecast'][0].keys())
        self.assertIn('LoadMw', data['HourlyLoadForecasts']['HourlyLoadForecast'][0].keys())

    def test_get_lmp_latest(self):
        price = self.c.get_lmp('NEMASSBOST')
        self.assertLess(price, 1500)
        self.assertGreater(price, -300)

    def test_get_lmp_hist(self):
        start_at = datetime(
            2015, 01, 01, 01, 1, 0, 0, tzinfo=pytz.timezone('US/Eastern')).astimezone(pytz.utc)
        end_at = start_at + timedelta(minutes=55)

        price_dict = self.c.get_lmp('NEMASSBOST', latest=False, start_at=start_at, end_at=end_at)
        self.assertEqual(len(price_dict), 11)
        self.assertEqual(price_dict[price_dict.keys()[0]], 42.72)
