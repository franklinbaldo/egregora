"""Stub types used by the test suite."""

from types import SimpleNamespace


class _SimpleStruct:
    def __init__(self, *args, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FunctionCall(_SimpleStruct):
    id: str | None = None
    name: str | None = None


Schema = FunctionDeclaration = Tool = FunctionResponse = Part = Content = _SimpleStruct
GenerateContentConfig = BatchJobSource = CreateBatchJobConfig = InlinedRequest = _SimpleStruct
EmbeddingsBatchJobSource = EmbedContentBatch = EmbedContentConfig = FileData = _SimpleStruct
BatchJob = JobError = _SimpleStruct
Type = SimpleNamespace(OBJECT="object", STRING="string", ARRAY="array", INTEGER="integer")
