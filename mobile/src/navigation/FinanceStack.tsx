/**
 * Finance tab stack (Issue #28).
 *
 *   Finance ──"+"──▶ ExpenseForm | RevenueForm  (whichever ledger is showing)
 *      └────tap row──▶ the same form, in edit mode
 */

import {createNativeStackNavigator} from '@react-navigation/native-stack';
import type {NativeStackScreenProps} from '@react-navigation/native-stack';
import React from 'react';

import {database} from '../db';
import type {Expense, Revenue} from '../db/models';
import ExpenseFormScreen from '../screens/finance/ExpenseFormScreen';
import FinanceScreen from '../screens/finance/FinanceScreen';
import RevenueFormScreen from '../screens/finance/RevenueFormScreen';
import {colors} from '../theme';

export type FinanceStackParamList = {
  Finance: undefined;
  ExpenseForm: {seasonId: string; expenseId?: string};
  RevenueForm: {seasonId: string; revenueId?: string};
};

const Stack = createNativeStackNavigator<FinanceStackParamList>();

type FinanceProps = NativeStackScreenProps<FinanceStackParamList, 'Finance'>;
type ExpenseProps = NativeStackScreenProps<FinanceStackParamList, 'ExpenseForm'>;
type RevenueProps = NativeStackScreenProps<FinanceStackParamList, 'RevenueForm'>;

function FinanceRoute({navigation}: FinanceProps) {
  return (
    <FinanceScreen
      onAddExpense={seasonId => navigation.navigate('ExpenseForm', {seasonId})}
      onAddRevenue={seasonId => navigation.navigate('RevenueForm', {seasonId})}
      onEditExpense={(expense: Expense) =>
        navigation.navigate('ExpenseForm', {
          seasonId: expense.seasonId,
          expenseId: expense.id,
        })
      }
      onEditRevenue={(revenue: Revenue) =>
        navigation.navigate('RevenueForm', {
          seasonId: revenue.seasonId,
          revenueId: revenue.id,
        })
      }
    />
  );
}

function ExpenseFormRoute({route, navigation}: ExpenseProps) {
  const {seasonId, expenseId} = route.params;
  const [expense, setExpense] = React.useState<Expense | undefined>();
  const [loading, setLoading] = React.useState(Boolean(expenseId));

  React.useEffect(() => {
    let cancelled = false;
    if (!expenseId) {
      setLoading(false);
      return;
    }
    database
      .get<Expense>('expenses')
      .find(expenseId)
      .then(found => {
        if (!cancelled) {
          setExpense(found);
          setLoading(false);
        }
      })
      .catch(() => {
        // Deleted elsewhere — most likely the diary entry behind an auto
        // expense was removed while this screen was opening.
        if (!cancelled) {
          navigation.goBack();
        }
      });
    return () => {
      cancelled = true;
    };
  }, [expenseId, navigation]);

  if (loading) {
    return null;
  }

  return (
    <ExpenseFormScreen
      seasonId={seasonId}
      expense={expense}
      onSaved={() => navigation.goBack()}
      onDeleted={() => navigation.goBack()}
      onCancel={() => navigation.goBack()}
    />
  );
}

function RevenueFormRoute({route, navigation}: RevenueProps) {
  const {seasonId, revenueId} = route.params;
  const [revenue, setRevenue] = React.useState<Revenue | undefined>();
  const [loading, setLoading] = React.useState(Boolean(revenueId));

  React.useEffect(() => {
    let cancelled = false;
    if (!revenueId) {
      setLoading(false);
      return;
    }
    database
      .get<Revenue>('revenues')
      .find(revenueId)
      .then(found => {
        if (!cancelled) {
          setRevenue(found);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          navigation.goBack();
        }
      });
    return () => {
      cancelled = true;
    };
  }, [revenueId, navigation]);

  if (loading) {
    return null;
  }

  return (
    <RevenueFormScreen
      seasonId={seasonId}
      revenue={revenue}
      onSaved={() => navigation.goBack()}
      onDeleted={() => navigation.goBack()}
      onCancel={() => navigation.goBack()}
    />
  );
}

export default function FinanceStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: {backgroundColor: colors.primary},
        headerTintColor: colors.textOnPrimary,
        headerTitleStyle: {fontWeight: '700'},
      }}>
      <Stack.Screen name="Finance" component={FinanceRoute} options={{title: 'Thu chi'}} />
      <Stack.Screen
        name="ExpenseForm"
        component={ExpenseFormRoute}
        options={({route}) => ({
          title: route.params?.expenseId ? 'Khoản chi' : 'Ghi khoản chi',
        })}
      />
      <Stack.Screen
        name="RevenueForm"
        component={RevenueFormRoute}
        options={({route}) => ({
          title: route.params?.revenueId ? 'Sửa khoản thu' : 'Ghi khoản thu',
        })}
      />
    </Stack.Navigator>
  );
}
