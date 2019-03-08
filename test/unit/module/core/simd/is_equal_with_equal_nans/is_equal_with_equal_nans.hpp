//==================================================================================================
/**
  EVE - Expressive Vector Engine
  Copyright 2019 Joel FALCOU

  Licensed under the MIT License <http://opensource.org/licenses/MIT>.
  SPDX-License-Identifier: MIT
**/
//==================================================================================================
#ifndef IS_EQUAL_WITH_EQUAL_NANS_HPP
#define IS_EQUAL_WITH_EQUAL_NANS_HPP

#include "test.hpp"
#include <tts/tests/relation.hpp>
#include <eve/function/simd/is_equal_with_equal_nans.hpp>
#include <eve/logical.hpp>
#include <eve/constant/nan.hpp>
#include <eve/wide.hpp>

using eve::fixed;

TTS_CASE_TPL("Check is_equal_with_equal_nans behavior on homogeneous wide",
             fixed<1>,
             fixed<2>,
             fixed<4>,
             fixed<8>,
             fixed<16>,
             fixed<32>,
             fixed<64>
            )
{
  using eve::wide;

  TTS_SETUP("A correctly initialized wide")
  {
    wide<Type, T> lhs([](int i, int c) { return i%3 ? Type(i%3)/Type(i%2) : Type(i); })
                , rhs([](int i, int c) { return i%2 ? Type(i%2)/Type(i%3) : Type(c-i); });
    wide < eve::logical < Type>, T >  ref([](int i, int c) { return eve::is_equal_with_equal_nans( i%3 ? Type(i%3)/Type(i%2) : Type(i),
                                                                                                   i%2 ? Type(i%2)/Type(i%3) : Type(c-i)); });
    TTS_SECTION("supports eve::is_equal_with_equal_nans") { TTS_EQUAL(ref, eve::is_equal_with_equal_nans(lhs, rhs)); }
  }
}

TTS_CASE_TPL("Check plus behavior on wide and scalar",
             fixed<1>,
             fixed<2>,
             fixed<4>,
             fixed<8>,
             fixed<16>,
             fixed<32>,
             fixed<64>)
{
  using eve::wide;

  TTS_SETUP("A correctly initialized wide and a scalar")
  {
    wide<Type, T>               lhs([](int i, int) { return Type(i%3 )/Type(i%2); });
    wide<eve::logical<Type>, T> ref([](int i, int) { return eve::is_equal_with_equal_nans(Type(i%3)/Type(i%2), eve::Nan<Type>()); });

    TTS_SECTION("supports eve::is_equal_with_equal_nans") { TTS_EQUAL(ref, eve::is_equal_with_equal_nans(lhs, eve::Nan<Type>())); }
    TTS_SECTION("supports eve::is_equal_with_equal_nans") { TTS_EQUAL(ref, eve::is_equal_with_equal_nans(eve::Nan<Type>(), lhs)); }
  }
}


#endif
