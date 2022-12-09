from django.db import models
import pandasdmx as sdmx


info = {
    "id": "STATCAN",
    "documentation": "http://data.un.org/Host.aspx?Content=API",
    "url": "http://ec.europa.eu/eurostat/SDMX/diss-web/rest",
    "name": "Statistics Canada",
    "supported": {"codelist": false, "preview": true}
    }
sdmx.add_source()

# Create your models here.
