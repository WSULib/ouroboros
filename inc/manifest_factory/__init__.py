# manifest-factory
import factory

# SETUP and INIT
iiif_manifest_factory_instance = factory.ManifestFactory()
# Where the resources live on the web
iiif_manifest_factory_instance.set_base_metadata_uri("http:/digital.library.wayne.edu/iiif_manifest")
# Where the resources live on disk
iiif_manifest_factory_instance.set_base_metadata_dir("/tmp/iiif_manifest")

# Default Image API information
iiif_manifest_factory_instance.set_base_image_uri("http://digital.library.wayne.edu/loris")
iiif_manifest_factory_instance.set_iiif_image_info(2.0, 2) # Version, ComplianceLevel

# 'warn' will print warnings, default level
# 'error' will turn off warnings
# 'error_on_warning' will make warnings into errors
iiif_manifest_factory_instance.set_debug("warn")