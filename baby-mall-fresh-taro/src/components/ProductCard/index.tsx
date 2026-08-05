import { Image, Text, View } from '@tarojs/components'
import { type Product } from '../../mock/catalog'
import { previewImages } from '../../utils/imagePreview'
import './index.scss'

type ProductCardProps = {
  product: Product
  onClick: (product: Product) => void
  onAdd?: (product: Product) => void
}

export function ProductCard({ product, onClick, onAdd }: ProductCardProps) {
  const skus = product.skus || []
  const totalStock = skus.length ? skus.reduce((total, sku) => total + sku.stock, 0) : null
  const minQty = skus.length ? Math.min(...skus.map((sku) => Math.max(1, sku.minQty || 1))) : 1
  const hasPriceRange = new Set(skus.map((sku) => sku.price)).size > 1

  return (
    <View className="product-card" onClick={() => onClick(product)}>
      <View className={`product-visual ${product.tone}`}>
        {product.imageUrl && (
          <Image
            className="product-image"
            src={product.imageUrl}
            mode="aspectFill"
            onClick={(event) => {
              event.stopPropagation()
              previewImages([product.imageUrl || ''], product.imageUrl)
            }}
          />
        )}
        {product.badge && <Text className="product-badge">{product.badge}</Text>}
      </View>
      <View className="product-body">
        <Text className="product-name">{product.name}</Text>
        <Text className="product-subtitle">{product.subtitle}</Text>
        <View className="product-facts">
          <Text className="product-stock">{totalStock === null ? product.stock : `\u5e93\u5b58 ${totalStock}`}</Text>
          {minQty > 1 && <Text className="product-min-qty">{`${minQty} \u4ef6\u8d77\u8ba2`}</Text>}
        </View>
        <View className="product-action">
          <View className="product-price-block">
            {hasPriceRange && <Text className="price-from">起</Text>}
            <Text className="price">{product.price.toFixed(2)}</Text>
            {product.marketPrice && product.marketPrice > product.price && <Text className="market-price">¥{product.marketPrice.toFixed(2)}</Text>}
          </View>
          {onAdd && (
            <View
              className="product-add-button"
              onClick={(event) => {
                event.stopPropagation()
                onAdd(product)
              }}
            >
              <Text className="product-add-symbol">+</Text>
            </View>
          )}
        </View>
      </View>
    </View>
  )
}
