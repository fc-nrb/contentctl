import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from contentctl.enrichments.attack_enrichment import AttackEnrichment
from contentctl.enrichments.cve_enrichment import CveEnrichment
from contentctl.helper.utils import Utils
from contentctl.input.yml_reader import YmlReader
from contentctl.objects.atomic import AtomicEnrichment
from contentctl.objects.baseline import Baseline
from contentctl.objects.config import validate
from contentctl.objects.dashboard import Dashboard
from contentctl.objects.data_source import DataSource
from contentctl.objects.deployment import Deployment
from contentctl.objects.detection import Detection
from contentctl.objects.enums import SecurityContentType
from contentctl.objects.investigation import Investigation
from contentctl.objects.lookup import Lookup, LookupAdapter
from contentctl.objects.macro import Macro
from contentctl.objects.playbook import Playbook
from contentctl.objects.security_content_object import SecurityContentObject
from contentctl.objects.story import Story


@dataclass
class DirectorOutputDto:
    # Atomic Tests are first because parsing them
    # is far quicker than attack_enrichment
    atomic_enrichment: AtomicEnrichment
    attack_enrichment: AttackEnrichment
    cve_enrichment: CveEnrichment
    detections: list[Detection]
    stories: list[Story]
    baselines: list[Baseline]
    investigations: list[Investigation]
    playbooks: list[Playbook]
    macros: list[Macro]
    lookups: list[Lookup]
    deployments: list[Deployment]
    dashboards: list[Dashboard]

    data_sources: list[DataSource]
    name_to_content_map: dict[str, SecurityContentObject] = field(default_factory=dict)
    uuid_to_content_map: dict[UUID, SecurityContentObject] = field(default_factory=dict)

    def addContentToDictMappings(self, content: SecurityContentObject):
        content_name = content.name

        if content_name in self.name_to_content_map:
            raise ValueError(
                f"Duplicate name '{content_name}' with paths:\n"
                f" - {content.file_path}\n"
                f" - {self.name_to_content_map[content_name].file_path}"
            )

        if content.id in self.uuid_to_content_map:
            raise ValueError(
                f"Duplicate id '{content.id}' with paths:\n"
                f" - {content.file_path}\n"
                f" - {self.uuid_to_content_map[content.id].file_path}"
            )

        if isinstance(content, Lookup):
            self.lookups.append(content)
        elif isinstance(content, Macro):
            self.macros.append(content)
        elif isinstance(content, Deployment):
            self.deployments.append(content)
        elif isinstance(content, Playbook):
            self.playbooks.append(content)
        elif isinstance(content, Baseline):
            self.baselines.append(content)
        elif isinstance(content, Investigation):
            self.investigations.append(content)
        elif isinstance(content, Story):
            self.stories.append(content)
        elif isinstance(content, Detection):
            self.detections.append(content)
        elif isinstance(content, Dashboard):
            self.dashboards.append(content)

        elif isinstance(content, DataSource):
            self.data_sources.append(content)
        else:
            raise Exception(f"Unknown security content type: {type(content)}")

        self.name_to_content_map[content_name] = content
        self.uuid_to_content_map[content.id] = content


class Director:
    input_dto: validate
    output_dto: DirectorOutputDto

    def __init__(self, output_dto: DirectorOutputDto) -> None:
        self.output_dto = output_dto

    def execute(self, input_dto: validate) -> None:
        self.input_dto = input_dto
        self.createSecurityContent(SecurityContentType.deployments)
        self.createSecurityContent(SecurityContentType.lookups)
        self.createSecurityContent(SecurityContentType.macros)
        self.createSecurityContent(SecurityContentType.stories)
        self.createSecurityContent(SecurityContentType.baselines)
        self.createSecurityContent(SecurityContentType.investigations)
        self.createSecurityContent(SecurityContentType.data_sources)
        self.createSecurityContent(SecurityContentType.playbooks)
        self.createSecurityContent(SecurityContentType.detections)
        self.createSecurityContent(SecurityContentType.dashboards)

    def createSecurityContent(self, contentType: SecurityContentType) -> None:
        if contentType in [
            SecurityContentType.deployments,
            SecurityContentType.lookups,
            SecurityContentType.macros,
            SecurityContentType.stories,
            SecurityContentType.baselines,
            SecurityContentType.investigations,
            SecurityContentType.playbooks,
            SecurityContentType.detections,
            SecurityContentType.data_sources,
            SecurityContentType.dashboards,
        ]:
            files = Utils.get_all_yml_files_from_directory(
                os.path.join(self.input_dto.path, str(contentType.name))
            )
            security_content_files = [f for f in files]
        else:
            raise (
                Exception(
                    f"Cannot createSecurityContent for unknown product {contentType}."
                )
            )

        validation_errors: list[tuple[Path, ValueError]] = []

        already_ran = False
        progress_percent = 0

        for index, file in enumerate(security_content_files):
            progress_percent = ((index + 1) / len(security_content_files)) * 100
            try:
                type_string = contentType.name.upper()
                modelDict = YmlReader.load_file(file)

                if contentType == SecurityContentType.lookups:
                    lookup = LookupAdapter.validate_python(
                        modelDict,
                        context={
                            "output_dto": self.output_dto,
                            "config": self.input_dto,
                        },
                    )
                    # lookup = Lookup.model_validate(modelDict, context={"output_dto":self.output_dto, "config":self.input_dto})
                    self.output_dto.addContentToDictMappings(lookup)

                elif contentType == SecurityContentType.macros:
                    macro = Macro.model_validate(
                        modelDict, context={"output_dto": self.output_dto}
                    )
                    self.output_dto.addContentToDictMappings(macro)

                elif contentType == SecurityContentType.deployments:
                    deployment = Deployment.model_validate(
                        modelDict, context={"output_dto": self.output_dto}
                    )
                    self.output_dto.addContentToDictMappings(deployment)

                elif contentType == SecurityContentType.playbooks:
                    playbook = Playbook.model_validate(
                        modelDict, context={"output_dto": self.output_dto}
                    )
                    self.output_dto.addContentToDictMappings(playbook)

                elif contentType == SecurityContentType.baselines:
                    baseline = Baseline.model_validate(
                        modelDict, context={"output_dto": self.output_dto}
                    )
                    self.output_dto.addContentToDictMappings(baseline)

                elif contentType == SecurityContentType.investigations:
                    investigation = Investigation.model_validate(
                        modelDict, context={"output_dto": self.output_dto}
                    )
                    self.output_dto.addContentToDictMappings(investigation)

                elif contentType == SecurityContentType.stories:
                    story = Story.model_validate(
                        modelDict, context={"output_dto": self.output_dto}
                    )
                    self.output_dto.addContentToDictMappings(story)

                elif contentType == SecurityContentType.detections:
                    detection = Detection.model_validate(
                        modelDict,
                        context={
                            "output_dto": self.output_dto,
                            "app": self.input_dto.app,
                        },
                    )
                    self.output_dto.addContentToDictMappings(detection)

                elif contentType == SecurityContentType.dashboards:
                    dashboard = Dashboard.model_validate(
                        modelDict, context={"output_dto": self.output_dto}
                    )
                    self.output_dto.addContentToDictMappings(dashboard)

                elif contentType == SecurityContentType.data_sources:
                    data_source = DataSource.model_validate(
                        modelDict, context={"output_dto": self.output_dto}
                    )
                    self.output_dto.addContentToDictMappings(data_source)

                else:
                    raise Exception(f"Unsupported type: [{contentType}]")

                if (
                    sys.stdout.isatty() and sys.stdin.isatty() and sys.stderr.isatty()
                ) or not already_ran:
                    already_ran = True
                    print(
                        f"\r{f'{type_string} Progress'.rjust(23)}: [{progress_percent:3.0f}%]...",
                        end="",
                        flush=True,
                    )

            except (ValidationError, ValueError) as e:
                relative_path = file.absolute().relative_to(
                    self.input_dto.path.absolute()
                )
                validation_errors.append((relative_path, e))

        print(
            f"\r{f'{contentType.name.upper()} Progress'.rjust(23)}: [{progress_percent:3.0f}%]...",
            end="",
            flush=True,
        )
        print("Done!")

        if len(validation_errors) > 0:
            errors_string = "\n\n".join(
                [
                    f"File: {e_tuple[0]}\nError: {str(e_tuple[1])}"
                    for e_tuple in validation_errors
                ]
            )
            # print(f"The following {len(validation_errors)} error(s) were found during validation:\n\n{errors_string}\n\nVALIDATION FAILED")
            # We quit after validation a single type/group of content because it can cause significant cascading errors in subsequent
            # types of content (since they may import or otherwise use it)
            raise Exception(
                f"The following {len(validation_errors)} error(s) were found during validation:\n\n{errors_string}\n\nVALIDATION FAILED"
            )
