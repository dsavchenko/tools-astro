#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import json
import os
import shutil
import sys

try:
    import numpy as np
    _numpy_available = True
except ImportError:
    _numpy_available = False

try:
    from oda_api.json import CustomJSONEncoder
except ImportError:
    from json import JSONEncoder as CustomJSONEncoder

_galaxy_wd = os.getcwd()


# In[1]:


source_list_url="https://renkulab.io/gitlab/astronomy/mmoda/integral-observed/-/raw/master/tlist.txt"
days_margin=3 # http://odahub.io/ontology#TimeIntervalDay


# In[ ]:


with open('inputs.json', 'r') as fd:
    inp_dic = json.load(fd)
if '_data_product' in inp_dic.keys():
    inp_pdic = inp_dic['_data_product']
else:
    inp_pdic = inp_dic

for vn, vv in inp_pdic.items():
    if vn != '_selector':
        globals()[vn] = type(globals()[vn])(vv)


# In[2]:


import requests
import pandas as pd


# In[3]:


from astropy.time import Time
from astropy import coordinates as coord


# In[1]:


# test!


# In[4]:


with open("list.txt", "w") as f:
    f.write(requests.get(source_list_url).text)


# In[5]:


d = pd.read_csv("list.txt", delimiter="|", names=["name", "ra", "dec", "time"])


# In[6]:


def parse_date(date):
    # print("date", date)
    year, month, day = map(float, date.split())
    hour = (day - int(day))*24
    return Time(dict(year=int(year), month=int(month), day=int(day), hour=int(hour)), format="ymdhms")
    
d['datetime'] = d.time.apply(parse_date)


# In[7]:


from oda_api.data_products import BinaryData, PictureProduct


# In[8]:


from matplotlib import pylab as plt


# In[9]:


from astroquery.heasarc import Heasarc, Conf
Conf.server.set('https://www.isdc.unige.ch/browse/w3query.pl')
heasarc = Heasarc()


# In[10]:


d


# In[24]:


def fix(s):
    a, b = s.rsplit(1)
    return a.replace(".", "") + " " + b

# d['ra'] = d.ra.apply(fix)

for test_name in ["QR And", "V407 Cyg", "AE Aqr", "MAXI J0911-635"]:
    ct = coord.SkyCoord.from_name(test_name)
    print("known", ct.ra.hms, ct.dec.dms)
    ref = d[d.name.str.strip() == test_name.replace(" ", "")]
    print(ref.ra, ref.dec)
    cr = coord.SkyCoord(ref.ra, ref.dec, unit=("hourangle", "deg"))
    print("ref", cr.ra.hms, cr.dec.dms)
    print(cr.separation(ct))
    assert cr.separation(ct).arcmin[0] < 1


# In[12]:


# NOTE: sometimes ra and dec are the same


# In[13]:


plt.figure()

problems = []

scws_by_source = {}

for i, r in d.iterrows():
    try:
        c = coord.SkyCoord(r.ra, r.dec, unit=('hourangle', 'degree'))
    except Exception as e:
        problems.append(f"problem parsing ra={r.ra} dec={r.dec} {e}")
        continue
        # s = r.ra.split()
        # c = coord.SkyCoord(" ".join(s[:3]), " ".join(s[3:]), unit=('hourangle', 'degree'))
    t1 = Time(r.datetime.mjd - days_margin, format='mjd').isot 
    t2 = Time(r.datetime.mjd + days_margin, format='mjd').isot 
    
    table = heasarc.query_object(
        f"{c.ra.deg} {c.dec.deg}", mission='integral_rev3_scw',                        
        radius='15 degree', time=f"{t1} .. {t2}",
        sortvar='START_DATE', resultmax=1000)
    
    name = r.to_dict()['name']
    print(name)
    if len(table) > 0:
        plt.bar(r.datetime.datetime, len(table), width=days_margin*100, label=name)
        
    scws_by_source[name] = [dict(r)['SCW_ID'] for r in table if r['SCW_ID'].endswith("0")]
    
    # print(table)
    
    # if len(table) > 0:
    #     break

plt.legend()
plt.xlabel("observation")
plt.ylabel("number of pointings")

plt.savefig("out.png")


# In[14]:


# scws_by_source


# In[15]:


problems


# In[16]:


output = '\n'.join(problems)
output


# In[17]:


import json


# In[18]:


observations_preview=PictureProduct.from_file("out.png") # http://odahub.io/ontology#ODAPictureProduct
log=output # http://odahub.io/ontology#ODATextProduct
observations=json.dumps(scws_by_source) # http://odahub.io/ontology#ODATextProduct


# In[ ]:


_simple_outs, _oda_outs = [], []
_galaxy_meta_data = {}
_oda_outs.append(('out_find-observations_observations_preview', 'observations_preview_galaxy.output', observations_preview))
_oda_outs.append(('out_find-observations_log', 'log_galaxy.output', log))
_oda_outs.append(('out_find-observations_observations', 'observations_galaxy.output', observations))

for _outn, _outfn, _outv in _oda_outs:
    _galaxy_outfile_name = os.path.join(_galaxy_wd, _outfn)
    if isinstance(_outv, str) and os.path.isfile(_outv):
        shutil.move(_outv, _galaxy_outfile_name)
        _galaxy_meta_data[_outn] = {'ext': '_sniff_'}
    elif getattr(_outv, "write_fits_file", None):
        _outv.write_fits_file(_galaxy_outfile_name)
        _galaxy_meta_data[_outn] = {'ext': 'fits'}
    elif getattr(_outv, "write_file", None):
        _outv.write_file(_galaxy_outfile_name)
        _galaxy_meta_data[_outn] = {'ext': '_sniff_'}
    else:
        with open(_galaxy_outfile_name, 'w') as fd:
            json.dump(_outv, fd, cls=CustomJSONEncoder)
        _galaxy_meta_data[_outn] = {'ext': 'json'}

for _outn, _outfn, _outv in _simple_outs:
    _galaxy_outfile_name = os.path.join(_galaxy_wd, _outfn)
    if isinstance(_outv, str) and os.path.isfile(_outv):
        shutil.move(_outv, _galaxy_outfile_name)
        _galaxy_meta_data[_outn] = {'ext': '_sniff_'}
    elif _numpy_available and isinstance(_outv, np.ndarray):
        with open(_galaxy_outfile_name, 'wb') as fd:
            np.savez(fd, _outv)
        _galaxy_meta_data[_outn] = {'ext': 'npz'}
    else:
        with open(_galaxy_outfile_name, 'w') as fd:
            json.dump(_outv, fd)
        _galaxy_meta_data[_outn] = {'ext': 'expression.json'}

with open(os.path.join(_galaxy_wd, 'galaxy.json'), 'w') as fd:
    json.dump(_galaxy_meta_data, fd)
print("*** Job finished successfully ***")

