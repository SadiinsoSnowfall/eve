//==================================================================================================
/*
  EVE - Expressive Vector Engine
  Copyright : EVE Project Contributors
  SPDX-License-Identifier: BSL-1.0
*/
//==================================================================================================
#pragma once

#include <eve/arch/arm/predef.hpp>
#include <eve/traits/as_integer.hpp>
#include <eve/detail/meta.hpp>
#include <type_traits>

namespace eve
{
  template<typename T>
  struct logical;
}

#if defined(EVE_HW_ARM)
namespace eve
{
  template <arithmetic_scalar_value T, typename Size>
  consteval auto find_register_type(as<T>, Size, eve::arm_64_)
  {
    if constexpr(std::is_same_v<T,float> && (Size::value <= 2))
    {
      return float32x2_t{};
    }
    else if constexpr(std::is_same_v<T,double> && (Size::value <= 1))
    {
      #if defined(SPY_SIMD_IS_ARM_ASIMD)
        return float64x1_t{};
      #else
        return emulated_{};
      #endif
    }
    else if constexpr( std::is_integral_v<T> )
    {
      constexpr bool signed_v = std::is_signed_v<T>;

      if      constexpr(  signed_v && (sizeof(T) == 1 ) && (Size::value <= 8) ) return int8x8_t{};
      else if constexpr(  signed_v && (sizeof(T) == 2 ) && (Size::value <= 4) ) return int16x4_t{};
      else if constexpr(  signed_v && (sizeof(T) == 4 ) && (Size::value <= 2) ) return int32x2_t{};
      else if constexpr(  signed_v && (sizeof(T) == 8 ) && (Size::value <= 1) ) return int64x1_t{};
      else if constexpr( !signed_v && (sizeof(T) == 1 ) && (Size::value <= 8) ) return uint8x8_t{};
      else if constexpr( !signed_v && (sizeof(T) == 2 ) && (Size::value <= 4) ) return uint16x4_t{};
      else if constexpr( !signed_v && (sizeof(T) == 4 ) && (Size::value <= 2) ) return uint32x2_t{};
      else if constexpr( !signed_v && (sizeof(T) == 8 ) && (Size::value <= 1) ) return uint64x1_t{};
    }
  }

  // ---------------------------------------------------------------------------------------------
  // NEON 128
  template<arithmetic_scalar_value T, typename Size>
  consteval auto find_register_type(as<T>, Size, eve::arm_128_)
  {
    if constexpr(std::is_same_v<T, float>)
    {
      return float32x4_t{};
    }
    else if constexpr(std::is_same_v<T, double>)
    {
      #if defined(SPY_SIMD_IS_ARM_ASIMD)
        return float64x2_t{};
      #else
        return emulated_{};
      #endif
    }
    else if constexpr(std::is_integral_v<T>)
    {
      constexpr bool signed_v = std::is_signed_v<T>;

      if      constexpr(  signed_v && (sizeof(T) == 1 ) && (Size::value == 16) ) return int8x16_t{};
      else if constexpr(  signed_v && (sizeof(T) == 2 ) && (Size::value == 8 ) ) return int16x8_t{};
      else if constexpr(  signed_v && (sizeof(T) == 4 ) && (Size::value == 4 ) ) return int32x4_t{};
      else if constexpr(  signed_v && (sizeof(T) == 8 ) && (Size::value == 2 ) ) return int64x2_t{};
      else if constexpr( !signed_v && (sizeof(T) == 1 ) && (Size::value == 16) ) return uint8x16_t{};
      else if constexpr( !signed_v && (sizeof(T) == 2 ) && (Size::value == 8 ) ) return uint16x8_t{};
      else if constexpr( !signed_v && (sizeof(T) == 4 ) && (Size::value == 4 ) ) return uint32x4_t{};
      else if constexpr( !signed_v && (sizeof(T) == 8 ) && (Size::value == 2 ) ) return uint64x2_t{};
    }
  }

  // ---------------------------------------------------------------------------------------------
  // logical cases
  template<typename T, typename Size, arm_abi ABI>
  consteval auto find_logical_register_type(as<T>, Size, ABI)
  {
    return find_register_type(as<as_integer_t<T, unsigned>>{}, Size{}, ABI{});
  }
}
#endif