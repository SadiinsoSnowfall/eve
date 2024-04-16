//==================================================================================================
/*
  EVE - Expressive Vector Engine
  Copyright : EVE Project Contributors
  SPDX-License-Identifier: BSL-1.0
*/
//==================================================================================================
#pragma once
#include <eve/arch.hpp>
#include <eve/traits/overload.hpp>
#include <eve/traits/bit_value.hpp>

namespace eve
{
  template<typename Options>
  struct bit_notor_t : strict_tuple_callable<bit_notor_t, Options>
  {
    template<eve::ordered_value T0, ordered_value T1, ordered_value... Ts>
    EVE_FORCEINLINE constexpr bit_value_t<T0, T1, Ts...>
    operator()(T0 t0, T1 t1, Ts...ts) const noexcept
    {
      return EVE_DISPATCH_CALL(t0, t1, ts...);
    }

    template<kumi::non_empty_product_type Tup>
    EVE_FORCEINLINE constexpr
    kumi::apply_traits_t<eve::bit_value,Tup>
    operator()(Tup const& t) const noexcept requires(kumi::size_v<Tup> >= 2) { return EVE_DISPATCH_CALL(t); }

    EVE_CALLABLE_OBJECT(bit_notor_t, bit_notor_);
  };

//================================================================================================
//! @addtogroup core_bitops
//! @{
//!   @var bit_notor
//!   @brief Computes the bitwise NOTOR of its arguments.
//!
//!   **Defined in Header**
//!
//!   @code
//!   #include <eve/module/core.hpp>
//!   @endcode
//!
//!   @groupheader{Callable Signatures}
//!
//!   @code
//!   namespace eve
//!   {
//!      template< eve::value T, eve::value Ts... >
//!      bit_value<T, Ts...> bit_notor(T x, Ts... xs) noexcept;
//!   }
//!   @endcode
//!
//!   **Parameters**
//!
//!     * `x`:       first [argument](@ref eve::value).
//!     * `xs...` :  other [arguments](@ref eve::value).
//!
//!    **Return value**
//!
//!     * The return value type is bit_value<T,  Ts...> Each parameter is converted
//        to this type and then:
//!
//!       * For two parameters it computes the  bitwise ANDNOT of the two parameters
//!       * For more than two parameters the call is  semantically equivalent to to `bit_notand(a0,
//!         bit_and(xs...))`
//!
//!  @groupheader{Example}
//!
//!  @godbolt{doc/core/bit_notor.cpp}
//!
//!  @groupheader{Semantic Modifiers}
//!
//!   * Masked Call
//!
//!     The call `eve::bit_notor[mask](x, ...)` provides a masked
//!     version of `bit_notor` which is
//!     equivalent to `if_else(mask, bit_notor(x, ...), x)`
//!
//! @}
//================================================================================================
  inline constexpr auto bit_notor = functor<bit_notor_t>;
}


#include <eve/module/core/regular/impl/bit_notor.hpp>

#if defined(EVE_INCLUDE_ARM_HEADER)
#  include <eve/module/core/regular/impl/simd/arm/neon/bit_notor.hpp>
#endif
