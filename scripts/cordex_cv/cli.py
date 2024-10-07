from . import create_cv, create_domain_id, create_driving_source_id, create_json_schema


def cv():
    print("creating CV")
    create_cv()


def domain_id():
    print("creating domain_id")
    create_domain_id()


def driving_source_id():
    print("creating driving_source_id")
    create_driving_source_id()


def json_schema():
    print("creating json schema")
    create_json_schema()
