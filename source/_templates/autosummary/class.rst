{# Custom template for class pages - Final version #}

{{ fullname | escape | underline }}

.. autoclass:: {{ fullname }}
   :members:
   :undoc-members:
   :no-inherited-members:
   :exclude-members: metadata
   :show-inheritance:
