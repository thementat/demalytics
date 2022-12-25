from django.db import models
import pandasdmx as sdmx

# Create your models here.

info = {
    "id": "STATCAN",
    "documentation": "http://data.un.org/Host.aspx?Content=API",
    "url": "http://ec.europa.eu/eurostat/SDMX/diss-web/rest",
    "name": "Statistics Canada",
    "supported": {"codelist": False, "preview": True}
    }
sdmx.source.add_source(info)


