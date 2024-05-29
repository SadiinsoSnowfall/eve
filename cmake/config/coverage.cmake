##==================================================================================================
##  EVE - Expressive Vector Engine
##  Copyright : EVE Project Contributors
##  SPDX-License-Identifier: BSL-1.0
##==================================================================================================


# add support for code coverage
if(CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    target_compile_options(eve_test INTERFACE -g -fprofile-instr-generate -fcoverage-mapping)
    target_link_options(eve_test INTERFACE -g -fprofile-instr-generate -fcoverage-mapping)
elseif(CMAKE_CXX_COMPILER_ID MATCHES "GNU")
    target_compile_options(eve_test INTERFACE -g --coverage)
    target_link_options(eve_test INTERFACE -g --coverage)
endif()
