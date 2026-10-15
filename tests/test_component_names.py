from scene_completion.component_names import source_name_supported


def test_physical_database_label_spacing_is_presentation_only():
    node={'name':'catalog_item表','kind':'internal_database'}
    assert source_name_supported(node,'服务向 catalog_item 表写入记录。')
    assert source_name_supported({**node,'kind':'external_database'},'从 catalog_item\t表读取。')
    assert not source_name_supported(node,'服务向 archived_catalog_item 表写入。')
    assert not source_name_supported(node,'服务向 schema.catalog_item 表写入。')
    assert not source_name_supported(node,'服务向 catalog_item\n表写入。')
    assert not source_name_supported(node,'服务向 catalog_item_archive 表写入。')


def test_display_normalization_does_not_license_semantic_aliases():
    assert not source_name_supported({'name':'商城系统','kind':'internal_service'},'商城购物系统')
    assert not source_name_supported({'name':'catalog_item表','kind':'internal_service'},'catalog_item 表')
    assert not source_name_supported({'name':'catalogItem表','kind':'internal_database'},'catalog_item 表')
    assert source_name_supported({'name':'CatalogService','kind':'internal_service'},'调用 CatalogService')
