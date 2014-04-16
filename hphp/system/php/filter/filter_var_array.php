<?php

function _filter_var_array_single($value, $filter, $options = array()) {
  $ret = filter_var($value, (int) $filter, $options);

  $flags = isset($options['flags']) ? $options['flags'] : 0;
  if ($flags & FILTER_FORCE_ARRAY && !is_array($ret)) {
    $ret = array($ret);
  }
  if ($flags & FILTER_REQUIRE_SCALAR && is_array($ret)) {
    $ret = false;
  }
  if ($flags & FILTER_REQUIRE_ARRAY && is_null($ret)) {
    $ret = array();
  }

  return $ret;
}

  // This doc comment block generated by idl/sysdoc.php
  /**
   * ( excerpt from http://php.net/manual/en/function.filter-var-array.php )
   *
   * This function is useful for retrieving many values without repetitively
   * calling filter_var().
   *
   * @data       mixed   An array with string keys containing the data to
   *                     filter.
   * @definition mixed   An array defining the arguments. A valid key is a
   *                     string containing a variable name and a valid value
   *                     is either a filter type, or an array optionally
   *                     specifying the filter, flags and options. If the
   *                     value is an array, valid keys are filter which
   *                     specifies the filter type, flags which specifies any
   *                     flags that apply to the filter, and options which
   *                     specifies any options that apply to the filter. See
   *                     the example below for a better understanding.
   *
   *                     This parameter can be also an integer holding a
   *                     filter constant. Then all values in the input array
   *                     are filtered by this filter.
   * @add_empty  mixed   Add missing keys as NULL to the return value.
   *
   * @return     mixed   An array containing the values of the requested
   *                     variables on success, or FALSE on failure. An array
   *                     value will be FALSE if the filter fails, or NULL if
   *                     the variable is not set.
   */
function filter_var_array($data, $definition = null, $add_empty = true) {

  if (!is_array($data)) {
    trigger_error('filter_var_array() expects parameter 1 to be array, '.
      gettype($data).' given', E_USER_WARNING);
    return null;
  }

  $default_filter = null;
  if (!is_array($definition)) {
    if ($definition === null) {
      $default_filter = FILTER_DEFAULT;
    } else if (is_int($definition)) {
      // A bit painful in php, exposing the IDs might be better if this is hot
      $ids = array_fill_keys(array_map('filter_id', filter_list()), null);
      if (!array_key_exists($definition, $ids)) {
        return false;
      }
      $default_filter = $definition;
    } else {
      return false;
    }

    $definition = array_fill_keys(array_keys($data), null);
  }

  $ret = array();
  foreach ($definition as $key => $def) {
    if ($key === "") {
      trigger_error(
        'filter_var_array(): Empty keys are not allowed in the '.
        'definition array',
        E_USER_WARNING
      );
      return false;
    }

    if (!array_key_exists($key, $data)) {
      if ($add_empty) {
        $ret[$key] = null;
      }
      continue;
    }

    $value = $data[$key];
    if ($default_filter) {
      $ret[$key] = _filter_var_array_single($value, $default_filter);
      continue;
    }

    if (!is_array($def)) {
      $ret[$key] = _filter_var_array_single($value, $def);
      continue;
    }

    if (!isset($def['filter'])) {
      $filter = FILTER_DEFAULT;
    } else {
      $filter = $def['filter'];
    }

    $ret[$key] = _filter_var_array_single($value, $filter, $def);
  }

  return $ret;
}
