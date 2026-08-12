/**
 * Supplies tab stack (Issue #24).
 *
 *   SupplyList ──"Nhập/Xuất/Kiểm kê"──▶ StockMovement
 *        │
 *        ├──tap card──▶ SupplyForm (sửa)
 *        └──"+"───────▶ SupplyForm (thêm)
 *
 * The movement button sits on the card rather than behind a tap-through,
 * because recording a purchase is the reason the farmer opened this tab;
 * editing the catalogue entry is not.
 */

import {createNativeStackNavigator} from '@react-navigation/native-stack';
import type {NativeStackScreenProps} from '@react-navigation/native-stack';
import React from 'react';

import {database} from '../db';
import type {Supply} from '../db/models';
import StockMovementScreen from '../screens/supplies/StockMovementScreen';
import SupplyFormScreen from '../screens/supplies/SupplyFormScreen';
import SupplyListScreen from '../screens/supplies/SupplyListScreen';
import {colors} from '../theme';

export type SuppliesStackParamList = {
  SupplyList: undefined;
  SupplyForm: {supplyId?: string};
  StockMovement: {supplyId: string};
};

const Stack = createNativeStackNavigator<SuppliesStackParamList>();

type ListProps = NativeStackScreenProps<SuppliesStackParamList, 'SupplyList'>;
type FormProps = NativeStackScreenProps<SuppliesStackParamList, 'SupplyForm'>;
type MovementProps = NativeStackScreenProps<SuppliesStackParamList, 'StockMovement'>;

/** Load a supply by id, or bail out if it vanished (deleted on another device). */
function useSupply(supplyId: string | undefined, onMissing: () => void) {
  const [supply, setSupply] = React.useState<Supply | undefined>();
  const [loading, setLoading] = React.useState(Boolean(supplyId));

  React.useEffect(() => {
    let cancelled = false;
    if (!supplyId) {
      setLoading(false);
      return;
    }
    database
      .get<Supply>('supplies')
      .find(supplyId)
      .then(found => {
        if (!cancelled) {
          setSupply(found);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          onMissing();
        }
      });
    return () => {
      cancelled = true;
    };
    // onMissing is a navigation callback and stable enough for this purpose;
    // including it would re-run the lookup on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supplyId]);

  return {supply, loading};
}

function SupplyListRoute({navigation}: ListProps) {
  return (
    <SupplyListScreen
      onCreateSupply={() => navigation.navigate('SupplyForm', {})}
      onSelectSupply={(s: Supply) => navigation.navigate('SupplyForm', {supplyId: s.id})}
      onMoveStock={(s: Supply) => navigation.navigate('StockMovement', {supplyId: s.id})}
    />
  );
}

function SupplyFormRoute({route, navigation}: FormProps) {
  const {supplyId} = route.params ?? {};
  const {supply, loading} = useSupply(supplyId, () => navigation.goBack());

  if (loading) {
    return null;
  }

  return (
    <SupplyFormScreen
      supply={supply}
      onSaved={() => navigation.goBack()}
      onDeleted={() => navigation.goBack()}
      onCancel={() => navigation.goBack()}
    />
  );
}

function StockMovementRoute({route, navigation}: MovementProps) {
  const {supplyId} = route.params;
  const {supply, loading} = useSupply(supplyId, () => navigation.goBack());

  if (loading || !supply) {
    return null;
  }

  return (
    <StockMovementScreen
      supply={supply}
      onDone={() => navigation.goBack()}
      onCancel={() => navigation.goBack()}
    />
  );
}

export default function SuppliesStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: {backgroundColor: colors.primary},
        headerTintColor: colors.textOnPrimary,
        headerTitleStyle: {fontWeight: '700'},
      }}>
      <Stack.Screen
        name="SupplyList"
        component={SupplyListRoute}
        options={{title: 'Vật tư'}}
      />
      <Stack.Screen
        name="SupplyForm"
        component={SupplyFormRoute}
        options={({route}) => ({
          title: route.params?.supplyId ? 'Sửa vật tư' : 'Thêm vật tư',
        })}
      />
      <Stack.Screen
        name="StockMovement"
        component={StockMovementRoute}
        options={{title: 'Giao dịch kho'}}
      />
    </Stack.Navigator>
  );
}
