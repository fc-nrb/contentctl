import re
import sys

from pydantic import ValidationError

from contentctl.objects.investigation import Investigation
from contentctl.input.yml_reader import YmlReader
from contentctl.objects.enums import SecurityContentType
from contentctl.objects.story import Story
from contentctl.objects.security_content_object import SecurityContentObject

class InvestigationBuilder():
    investigation: Investigation

    def setObject(self, path: str, contentNameToDictMap:dict[str,SecurityContentObject]={}) -> None:
        yml_dict = YmlReader.load_file(path)
        try:
            self.investigation = Investigation.model_validate(yml_dict, context=contentNameToDictMap)
        except ValidationError as e:
            print(f'Validation Error for file {path}' )
            print(e)
            sys.exit(1)

    def reset(self) -> None:
        self.investigation = None


    def getObject(self) -> Investigation:
        return self.investigation


    def addInputs(self) -> None:
        pattern = r"\$([^\s.]*)\$"
        inputs = []

        for input in re.findall(pattern, self.investigation.search):
            inputs.append(input)

        self.investigation.inputs = inputs
