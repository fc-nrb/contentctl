from __future__ import annotations

from pydantic import field_validator, ValidationInfo, model_validator, FilePath, model_serializer, Field, NonNegativeInt, computed_field
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Optional, Any, Union, Literal, Annotated, Self
import re
import csv
import abc
from functools import cached_property
import pathlib
if TYPE_CHECKING:
    from contentctl.input.director import DirectorOutputDto
    from contentctl.objects.config import validate
from contentctl.objects.security_content_object import SecurityContentObject

# This section is used to ignore lookups that are NOT  shipped with ESCU app but are used in the detections. Adding exclusions here will so that contentctl builds will not fail.
LOOKUPS_TO_IGNORE = set(["outputlookup"])
LOOKUPS_TO_IGNORE.add("ut_shannon_lookup") #In the URL toolbox app which is recommended for ESCU
LOOKUPS_TO_IGNORE.add("identity_lookup_expanded") #Shipped with the Asset and Identity Framework
LOOKUPS_TO_IGNORE.add("cim_corporate_web_domain_lookup") #Shipped with the Asset and Identity Framework
LOOKUPS_TO_IGNORE.add("alexa_lookup_by_str") #Shipped with the Asset and Identity Framework
LOOKUPS_TO_IGNORE.add("interesting_ports_lookup") #Shipped with the Asset and Identity Framework
LOOKUPS_TO_IGNORE.add("asset_lookup_by_str") #Shipped with the Asset and Identity Framework
LOOKUPS_TO_IGNORE.add("admon_groups_def") #Shipped with the SA-admon addon
LOOKUPS_TO_IGNORE.add("identity_lookup_expanded") #Shipped with the Enterprise Security

#Special case for the Detection "Exploit Public Facing Application via Apache Commons Text"
LOOKUPS_TO_IGNORE.add("=") 
LOOKUPS_TO_IGNORE.add("other_lookups") 


class Lookup_Type(StrEnum):
    csv = auto()
    kvstore = auto()
    mlmodel = auto()



# TODO (#220): Split Lookup into 2 classes
class Lookup(SecurityContentObject, abc.ABC):    
    default_match: Optional[bool] = None
    # Per the documentation for transforms.conf, EXACT should not be specified in this list,
    # so we include only WILDCARD and CIDR
    match_type: list[Annotated[str, Field(pattern=r"(^WILDCARD|CIDR)\(.+\)$")]] = Field(default=[])
    min_matches: None | NonNegativeInt = Field(default=None)
    max_matches: None | Annotated[NonNegativeInt, Field(ge=1, le=1000)] = Field(default=None)    
    case_sensitive_match: None | bool = Field(default=None)
    


    @model_serializer
    def serialize_model(self):
        #Call parent serializer
        super_fields = super().serialize_model()

        #All fields custom to this model
        model= {
            
            "default_match": "true" if self.default_match is True else "false",
            "match_type": self.match_type,
            "min_matches": self.min_matches,
            "case_sensitive_match": "true" if self.case_sensitive_match is True else "false",
        }
        
        #return the model
        model.update(super_fields)
        return model

    @model_validator(mode="before")
    def fix_lookup_path(cls, data:Any, info: ValidationInfo)->Any:
        if data.get("filename"):
            config:validate = info.context.get("config",None)
            if config is not None:
                data["filename"] = config.path / "lookups/" / data["filename"]
            else:
                raise ValueError("config required for constructing lookup filename, but it was not")
        return data


    
    
        
    @staticmethod
    def get_lookups(text_field: str, director:DirectorOutputDto, ignore_lookups:set[str]=LOOKUPS_TO_IGNORE)->list[Lookup]:
        inputLookupsToGet = set(re.findall(r'inputlookup(?:\s*(?:(?:append|strict|start|max)\s*=\s*(?:true|t|false|f))){0,4}\s+([^\s]+)', text_field))
        outputLookupsToGet = set(re.findall(r'outputlookup(?:\s*(?:(?:append|create_empty|override_if_empty|max|key_field|allow_updates|createinapp|create_context|output_format)\s*=\s*[^\s]*))*\s+([^\s]+)',text_field))
        # Don't match inputlookup or outputlookup. Allow local=true or update=true or local=t or update=t 
        lookups_to_get = set(re.findall(r'(?:(?<!output)(?<!input))lookup(?:\s*(?:(?:local|update)\s*=\s*(?:true|t|false|f))){0,2}\s+([^\s]+)', text_field))
        #lookups_to_get = set(re.findall(r'[^output]lookup (?:update=true)?(?:append=t)?\s*([^\s]*)', text_field))
        #lookups_to_get = set(re.findall(r'(?!output)lookup(?:\s*(?:(?:local|update)\s*=\s*(?:true|t))){0,2}\s+([^\s]+)', text_field))
        
        
        
        
        input_lookups = Lookup.mapNamesToSecurityContentObjects(list(inputLookupsToGet-LOOKUPS_TO_IGNORE), director)
        output_lookups = Lookup.mapNamesToSecurityContentObjects(list(outputLookupsToGet-LOOKUPS_TO_IGNORE), director)
    
        

        my_lookups = Lookup.mapNamesToSecurityContentObjects(list(lookups_to_get-LOOKUPS_TO_IGNORE), director)


            
        return my_lookups






class CSVLookup(Lookup):
    lookup_type: Literal[Lookup_Type.csv]
    

    @model_validator(mode="after")
    def ensure_lookup_file_exists(self)->Self:
        if not self.filename.exists():
            raise ValueError(f"Expected lookup filename {self.filename} does not exist")
        return self

    @computed_field
    @cached_property
    def filename(self)->FilePath:
        if self.file_path is None:
            raise ValueError("Cannot get the filename of the lookup CSV because the YML file_path attribute is None")
        
        csv_file = self.file_path.parent / f"{self.file_path.stem}.csv"
        return csv_file
    
    @computed_field
    @cached_property
    def app_filename(self)->FilePath:
        '''
        We may consider two options:
        1. Always apply the datetime stamp to the end of the file. This makes the code easier
        2. Only apply the datetime stamp if it is version > 1.  This makes the code a small fraction
        more complicated, but preserves longstanding CSV that have not been modified in a long time
        '''
        return pathlib.Path(f"{self.filename.stem}_{self.date.year}{self.date.month:02}{self.date.day:02}.csv")



    @model_serializer
    def serialize_model(self):
        #Call parent serializer
        super_fields = super().serialize_model()

        #All fields custom to this model
        model= {
            "filename": self.filename.name
        }
        
        #return the model
        model.update(super_fields)
        return model
    
    @model_validator(mode="after")
    def ensure_correct_csv_structure(self)->Self:
        
        
        if self.filename.suffix != ".csv":
            raise ValueError(f"All Lookup files must be CSV files and end in .csv.  The following file does not: '{self.filename}'")
        
    

        # https://docs.python.org/3/library/csv.html#csv.DictReader
        # Column Names (fieldnames) determine by the number of columns in the first row.
        # If a row has MORE fields than fieldnames, they will be dumped in a list under the key 'restkey' - this should throw an Exception
        # If a row has LESS fields than fieldnames, then the field should contain None by default. This should also throw an exception.    
        csv_errors:list[str] = []
        with open(self.filename, "r") as csv_fp:
            RESTKEY = "extra_fields_in_a_row"
            csv_dict = csv.DictReader(csv_fp, restkey=RESTKEY)            
            if csv_dict.fieldnames is None:
                raise ValueError(f"Error validating the CSV referenced by the lookup: {self.filename}:\n\t"
                                 "Unable to read fieldnames from CSV. Is the CSV empty?\n"
                                 "  Please try opening the file with a CSV Editor to ensure that it is correct.")
            # Remember that row 1 has the headers and we do not iterate over it in the loop below
            # CSVs are typically indexed starting a row 1 for the header.
            for row_index, data_row in enumerate(csv_dict):
                row_index+=2
                if len(data_row.get(RESTKEY,[])) > 0:
                    csv_errors.append(f"row [{row_index}] should have [{len(csv_dict.fieldnames)}] columns,"
                                      f" but instead had [{len(csv_dict.fieldnames) + len(data_row.get(RESTKEY,[]))}].")
                
                for column_index, column_name in enumerate(data_row):
                    if data_row[column_name] is None:
                        csv_errors.append(f"row [{row_index}] should have [{len(csv_dict.fieldnames)}] columns, "
                                          f"but instead had [{column_index}].")
        if len(csv_errors) > 0:
            err_string = '\n\t'.join(csv_errors)
            raise ValueError(f"Error validating the CSV referenced by the lookup: {self.filename}:\n\t{err_string}\n"
                             f"  Please try opening the file with a CSV Editor to ensure that it is correct.")
    
        return self



class KVStoreLookup(Lookup):
    lookup_type: Literal[Lookup_Type.kvstore]
    collection: str = Field(description="Name of the KVStore Collection. Note that collection MUST equal the name.")
    fields: list[str] = Field(description="The names of the fields/headings for the KVStore.", min_length=1)


    @model_validator(mode="after")
    def validate_collection(self)->Self:
        if self.collection != self.name:
            raise ValueError("Collection MUST be the same as Name of the lookup, but they do not match")
        return self

    @model_serializer
    def serialize_model(self):
        #Call parent serializer
        super_fields = super().serialize_model()

        #All fields custom to this model
        model= {
            "collection": self.collection,
            "fields_list": ", ".join(self.fields)
        }
        
        #return the model
        model.update(super_fields)
        return model

class MlModel(Lookup):
    lookup_type: Literal[Lookup_Type.mlmodel]
    



